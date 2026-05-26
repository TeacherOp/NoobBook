"""
Transcription Service - ElevenLabs Speech-to-Text support.

Educational Note: This service generates single-use tokens for the frontend
to connect to ElevenLabs' real-time WebSocket transcription API.

Security Note: We never expose the API key to the frontend. Instead, we
generate a short-lived token that the frontend uses for WebSocket auth.
"""
import logging
import os
from typing import Iterable, List, Optional
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)

# ElevenLabs Scribe v2 realtime caps: up to 50 keyterms, ≤20 chars each.
# Source: realtime WebSocket handshake docs.
_MAX_KEYTERMS = 50
_MAX_KEYTERM_LEN = 20


def _sanitize_keyterms(raw: Optional[Iterable[str]]) -> List[str]:
    """Dedupe, strip, drop empties, truncate, and cap to Scribe's limits.

    Returns a list ready to be appended as repeated `&keyterms=` params.
    Order is preserved (first occurrence wins) so a frontend caller can
    front-load the most important terms (project name first, then
    source filenames) and trust the cap doesn't drop them.
    """
    if not raw:
        return []
    seen: set[str] = set()
    out: List[str] = []
    for term in raw:
        if not isinstance(term, str):
            continue
        cleaned = term.strip()
        if not cleaned:
            continue
        # Truncate per-term to Scribe's 20-char cap.
        if len(cleaned) > _MAX_KEYTERM_LEN:
            cleaned = cleaned[:_MAX_KEYTERM_LEN].rstrip()
            if not cleaned:
                continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(cleaned)
        if len(out) >= _MAX_KEYTERMS:
            break
    return out


class TranscriptionService:
    """
    Service class for ElevenLabs speech-to-text configuration.

    Educational Note: ElevenLabs real-time transcription uses WebSocket
    connections directly from the browser. This service provides the
    configuration needed for the frontend to establish that connection.
    """

    # ElevenLabs WebSocket endpoint and model
    WEBSOCKET_URL = "wss://api.elevenlabs.io/v1/speech-to-text/realtime"
    DEFAULT_MODEL = "scribe_v2_realtime"

    # Supported audio configurations for ElevenLabs
    SAMPLE_RATE = 16000  # 16kHz recommended
    ENCODING = "pcm_s16le"  # 16-bit PCM little-endian

    def __init__(self):
        """Initialize the transcription service."""
        pass

    def generate_scribe_token(self) -> str:
        """
        Generate a single-use token for ElevenLabs realtime transcription.

        Educational Note: ElevenLabs requires a single-use token for client-side
        WebSocket connections. This token is generated server-side using the API key,
        and expires after 15 minutes. This keeps the API key secure on the server.

        Returns:
            Single-use token string

        Raises:
            ValueError: If API key is not configured
            Exception: If token generation fails
        """
        api_key = os.getenv('ELEVENLABS_API_KEY')

        if not api_key:
            logger.error("ELEVENLABS_API_KEY not found in environment")
            raise ValueError("ELEVENLABS_API_KEY not found in environment")

        # Request a single-use token from ElevenLabs
        response = requests.post(
            "https://api.elevenlabs.io/v1/single-use-token/realtime_scribe",
            headers={"xi-api-key": api_key},
            timeout=10
        )

        if response.status_code != 200:
            logger.error("Failed to generate ElevenLabs scribe token: %s", response.text)
            raise Exception(f"Failed to generate token: {response.text}")

        data = response.json()
        return data.get("token")

    def get_elevenlabs_config(
        self,
        keyterms: Optional[Iterable[str]] = None,
    ) -> dict:
        """
        Get ElevenLabs configuration for frontend WebSocket connection.

        Generates a fresh single-use token, builds the realtime URL with
        VAD commit strategy and `no_verbatim=true` (server-side filler
        and disfluency removal — the cleanest fix for "um/uh" landing in
        chat input). Optional keyterms bias recognition toward
        domain-specific words; sanitized to Scribe's limits (50 terms,
        ≤20 chars each). Token expires after 15 minutes.

        Note: keyterms incur a documented 20% pricing premium per
        ElevenLabs — callers should only pass them when they actually
        improve recognition (project name, selected source filenames).
        """
        token = self.generate_scribe_token()

        # Educational Note: Using VAD (Voice Activity Detection) for
        # automatic speech segmentation — commits transcript when
        # silence is detected. `no_verbatim=true` asks Scribe to drop
        # filler words, false starts, and stutters before commit,
        # cutting cleanup latency to zero (vs a post-pass LLM call).
        url_parts = [
            f"{self.WEBSOCKET_URL}",
            f"?model_id={self.DEFAULT_MODEL}",
            f"&token={token}",
            f"&audio_format=pcm_{self.SAMPLE_RATE}",
            f"&commit_strategy=vad",
            f"&no_verbatim=true",
        ]
        sanitized = _sanitize_keyterms(keyterms)
        for term in sanitized:
            # URL-encode the term value but keep `&keyterms=` literal.
            # ElevenLabs accepts repeated params; both `requests` and
            # standard parsers treat this as a list.
            url_parts.append(f"&keyterms={quote(term, safe='')}")

        websocket_url = "".join(url_parts)

        # Educational Note: Only return the token and config needed by frontend
        # Never expose the API key to the client - it stays server-side only
        return {
            "websocket_url": websocket_url,
            "model_id": self.DEFAULT_MODEL,
            "sample_rate": self.SAMPLE_RATE,
            "encoding": self.ENCODING,
            "no_verbatim": True,
            "keyterms": sanitized,
        }

    def is_configured(self) -> bool:
        """
        Check if ElevenLabs API key is configured.

        Returns:
            True if API key is set, False otherwise
        """
        return bool(os.getenv('ELEVENLABS_API_KEY'))
