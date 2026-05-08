"""
GPT Image 2 Service - OpenAI's image generation model.

Default image generator for all studio surfaces (ad creatives, social posts,
infographics, blog images, email banners, website assets).

Two endpoints:
- client.images.generate(...) — text-to-image
- client.images.edit(model, image=[...], prompt, ...) — multi-reference (used
  when a brand logo should be incorporated)

Streams partial images (partial_images=2) so the studio panels can show a
live preview while the final image renders. Each partial b64 frame is
forwarded to an optional `on_partial(b64_json, idx)` callback so callers
can upload it to Supabase and append to the job record.

If the model resolves to an unsupported / unauthorized error (the model is
brand new and may need org verification), callers can fall back to Gemini
via imagen_service. This service surfaces the signal via the
`fallback_to_gemini` flag in its return dict.
"""
import base64
import io
import logging
import os
import time
from datetime import datetime
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


# Per-image USD prices — see docs at platform.openai.com/docs/guides/images.
# Keyed by (size, quality). Sizes here match what _size_for can return.
_PRICING = {
    ("1024x1024", "low"): 0.006,
    ("1024x1024", "medium"): 0.053,
    ("1024x1024", "high"): 0.211,
    ("1024x1536", "low"): 0.005,
    ("1024x1536", "medium"): 0.041,
    ("1024x1536", "high"): 0.165,
    ("1536x1024", "low"): 0.005,
    ("1536x1024", "medium"): 0.041,
    ("1536x1024", "high"): 0.165,
    # 2K / 4K — official table only lists the three popular sizes; for
    # higher resolutions we approximate by the ratio of total pixels vs
    # 1024x1024. Conservative enough for cost reporting.
}

# Aspect ratio + resolution → GPT Image 2 size (must satisfy edges multiple
# of 16, max edge 3840px, ratio ≤ 3:1, total pixels 655,360–8,294,400).
# 4K square is capped at 2880² because 3840² exceeds the 8.29M-pixel cap.
_SIZE_TABLE = {
    ("1:1", "1K"): "1024x1024",
    ("1:1", "2K"): "2048x2048",
    ("1:1", "4K"): "2880x2880",
    ("16:9", "1K"): "1536x1024",
    ("16:9", "2K"): "2048x1152",
    ("16:9", "4K"): "3840x2160",
    ("9:16", "1K"): "1024x1536",
    ("9:16", "2K"): "1152x2048",
    ("9:16", "4K"): "2160x3840",
}

# Errors that signal "GPT Image 2 won't work on this key right now" — for
# these the caller should transparently fall back to Gemini. See OpenAI's
# org-verification doc: gpt-image-2 requires verification before use.
# Also includes account-level billing/quota errors: these are not prompt-
# or model-specific, so retrying on the same OpenAI key won't help, but
# Gemini (different account) is unaffected.
_FALLBACK_ERROR_CODES = {
    "model_not_found",
    "unauthorized_organization",
    "image_generation_user_not_allowed",
    "must_be_verified_to_use_model",
    "organization_must_be_verified",
    "billing_hard_limit_reached",
    "insufficient_quota",
    "account_deactivated",
}


PartialCallback = Callable[[str, int], None]


class GPTImageService:
    """Provider for OpenAI GPT Image 2 generation + reference-image edits."""

    MODEL_ID = "gpt-image-2-2026-04-21"
    DEFAULT_QUALITY = "medium"
    DEFAULT_PARTIAL_IMAGES = 2

    MAX_RETRIES = 2  # network / 5xx retries; the model itself is deterministic
    RETRY_BASE_DELAY = 2

    def __init__(self):
        self._client = None

    def is_configured(self) -> bool:
        return bool(os.getenv("OPENAI_API_KEY"))

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY not configured")
            self._client = OpenAI(api_key=api_key)
        return self._client

    @staticmethod
    def _size_for(aspect_ratio: Optional[str], resolution: Optional[str]) -> str:
        ar = aspect_ratio or "1:1"
        res = resolution or "1K"
        return _SIZE_TABLE.get((ar, res), "1024x1024")

    @staticmethod
    def _price_for(size: str, quality: str) -> float:
        if (size, quality) in _PRICING:
            return _PRICING[(size, quality)]
        # Approximate: scale by total-pixel ratio vs the 1024² baseline.
        try:
            w, h = (int(x) for x in size.split("x"))
            base = _PRICING.get(("1024x1024", quality), 0.053)
            return base * (w * h) / (1024 * 1024)
        except Exception:
            return 0.053  # medium 1024² fallback

    @staticmethod
    def _is_fallback_error(err: Exception) -> bool:
        # Map OpenAI SDK errors to the fallback signal. The SDK exposes
        # err.code and err.status_code; we care about model availability
        # and verification gates.
        from openai import (
            APIStatusError,
            BadRequestError,
            NotFoundError,
            PermissionDeniedError,
        )
        code = getattr(err, "code", None) or ""
        body = getattr(err, "body", None) or {}
        if isinstance(body, dict):
            code = code or (body.get("error", {}) or {}).get("code", "") or body.get("code", "")

        if code in _FALLBACK_ERROR_CODES:
            return True
        if isinstance(err, NotFoundError):
            return True
        if isinstance(err, PermissionDeniedError):
            return True
        # 400 with a "must verify" message — best effort string match
        if isinstance(err, BadRequestError):
            msg = str(err).lower()
            if "verif" in msg or "not allowed" in msg or "model" in msg and "not" in msg:
                return True
        if isinstance(err, APIStatusError) and getattr(err, "status_code", 0) == 404:
            return True
        return False

    @staticmethod
    def _is_transient_error(err: Exception) -> bool:
        from openai import APIConnectionError, APIStatusError, RateLimitError
        if isinstance(err, (APIConnectionError, RateLimitError)):
            return True
        if isinstance(err, APIStatusError):
            sc = getattr(err, "status_code", 0)
            return sc in (500, 502, 503, 504)
        return False

    def _call_with_retry(self, fn, description: str = "API call"):
        last_err = None
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                return fn()
            except Exception as err:  # noqa: BLE001 — we re-raise selectively
                last_err = err
                if not self._is_transient_error(err) or attempt == self.MAX_RETRIES:
                    raise
                delay = self.RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(
                    "%s transient failure (attempt %d/%d), retrying in %ds: %s",
                    description, attempt + 1, self.MAX_RETRIES + 1, delay, err,
                )
                time.sleep(delay)
        if last_err:
            raise last_err

    def _consume_stream(
        self,
        stream,
        on_partial: Optional[PartialCallback],
    ) -> Optional[bytes]:
        """
        Consume a streaming images response. Forwards partial frames to
        on_partial and returns the final image bytes.

        Stream events (per OpenAI docs):
          - type="image_generation.partial_image", b64_json, partial_image_index
          - type="image_generation.completed", b64_json (final)

        Different SDK versions may use slightly different event names; we
        match by suffix to be defensive.
        """
        final_b64: Optional[str] = None
        for event in stream:
            etype = getattr(event, "type", "") or ""
            b64 = getattr(event, "b64_json", None)
            idx = getattr(event, "partial_image_index", None)
            if etype.endswith("partial_image") and b64:
                if on_partial is not None:
                    try:
                        on_partial(b64, idx if idx is not None else 0)
                    except Exception:
                        logger.exception("on_partial callback raised — continuing")
            elif b64:
                # Final frame (or unspecified completed event with bytes).
                final_b64 = b64
        if final_b64 is None:
            return None
        return base64.b64decode(final_b64)

    def _record_cost(self, project_id: Optional[str], size: str, quality: str, n: int):
        if not project_id:
            return
        try:
            from app.utils.cost_tracking import add_image_usage
            add_image_usage(
                project_id=project_id,
                model=self.MODEL_ID,
                size=size,
                quality=quality,
                n=n,
                unit_cost=self._price_for(size, quality),
            )
        except Exception:
            logger.exception("Failed to record GPT Image 2 cost")

    def _build_result(
        self,
        success: bool,
        *,
        image_bytes: Optional[bytes] = None,
        filename_prefix: str = "image",
        error: Optional[str] = None,
        fallback_to_gemini: bool = False,
    ) -> Dict[str, Any]:
        if success and image_bytes is not None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            return {
                "success": True,
                "filename": f"{filename_prefix}_{timestamp}.png",
                "image_bytes": image_bytes,
                "content_type": "image/png",
            }
        return {
            "success": False,
            "error": error or "Unknown error",
            "fallback_to_gemini": fallback_to_gemini,
        }

    def _generate(
        self,
        prompt: str,
        size: str,
        quality: str,
        on_partial: Optional[PartialCallback],
    ) -> bytes:
        """Streaming text-to-image. Returns final image bytes."""
        client = self._get_client()
        stream = self._call_with_retry(
            lambda: client.images.generate(
                model=self.MODEL_ID,
                prompt=prompt,
                size=size,
                quality=quality,
                n=1,
                stream=True,
                partial_images=self.DEFAULT_PARTIAL_IMAGES,
            ),
            description="GPT Image 2 generate",
        )
        image_bytes = self._consume_stream(stream, on_partial)
        if image_bytes is None:
            raise RuntimeError("GPT Image 2 stream returned no final image")
        return image_bytes

    def _edit(
        self,
        prompt: str,
        reference_bytes: bytes,
        reference_mime_type: str,
        size: str,
        quality: str,
        on_partial: Optional[PartialCallback],
    ) -> bytes:
        """Streaming image edit with a reference image (e.g. brand logo)."""
        client = self._get_client()
        ref_file = io.BytesIO(reference_bytes)
        # OpenAI SDK accepts file-like objects; assign a name so it's sent
        # with a sensible content-type.
        ext = "png" if "png" in (reference_mime_type or "").lower() else "jpg"
        ref_file.name = f"reference.{ext}"

        stream = self._call_with_retry(
            lambda: client.images.edit(
                model=self.MODEL_ID,
                image=[ref_file],
                prompt=prompt,
                size=size,
                quality=quality,
                stream=True,
                partial_images=self.DEFAULT_PARTIAL_IMAGES,
            ),
            description="GPT Image 2 edit",
        )
        image_bytes = self._consume_stream(stream, on_partial)
        if image_bytes is None:
            raise RuntimeError("GPT Image 2 edit stream returned no final image")
        return image_bytes

    def generate_image_bytes(
        self,
        prompt: str,
        filename_prefix: str = "image",
        aspect_ratio: Optional[str] = None,
        resolution: Optional[str] = None,
        *,
        quality: str = DEFAULT_QUALITY,
        project_id: Optional[str] = None,
        on_partial: Optional[PartialCallback] = None,
    ) -> Dict[str, Any]:
        if not prompt or not prompt.strip():
            return self._build_result(False, error="No prompt provided")

        size = self._size_for(aspect_ratio, resolution)
        try:
            image_bytes = self._generate(prompt, size, quality, on_partial)
        except Exception as err:
            if self._is_fallback_error(err):
                logger.warning("GPT Image 2 unavailable (%s) — fallback to Gemini", err)
                return self._build_result(False, error=str(err), fallback_to_gemini=True)
            logger.exception("GPT Image 2 generate failed")
            return self._build_result(False, error=str(err))

        self._record_cost(project_id, size, quality, 1)
        return self._build_result(True, image_bytes=image_bytes, filename_prefix=filename_prefix)

    def generate_image_with_reference(
        self,
        prompt: str,
        reference_image_bytes: bytes,
        reference_mime_type: str = "image/png",
        filename_prefix: str = "image",
        aspect_ratio: Optional[str] = None,
        resolution: Optional[str] = None,
        *,
        quality: str = DEFAULT_QUALITY,
        project_id: Optional[str] = None,
        on_partial: Optional[PartialCallback] = None,
    ) -> Dict[str, Any]:
        if not prompt or not prompt.strip():
            return self._build_result(False, error="No prompt provided")
        if not reference_image_bytes:
            return self._build_result(False, error="No reference image provided")

        size = self._size_for(aspect_ratio, resolution)
        try:
            image_bytes = self._edit(
                prompt, reference_image_bytes, reference_mime_type, size, quality, on_partial,
            )
        except Exception as err:
            if self._is_fallback_error(err):
                logger.warning("GPT Image 2 edit unavailable (%s) — fallback to Gemini", err)
                return self._build_result(False, error=str(err), fallback_to_gemini=True)
            logger.exception("GPT Image 2 edit failed")
            return self._build_result(False, error=str(err))

        self._record_cost(project_id, size, quality, 1)
        return self._build_result(True, image_bytes=image_bytes, filename_prefix=filename_prefix)


gpt_image_service = GPTImageService()
