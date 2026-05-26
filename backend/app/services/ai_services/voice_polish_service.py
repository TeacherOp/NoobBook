"""
Voice Polish Service - Final cleanup pass for transcribed speech.

ElevenLabs Scribe's `no_verbatim=true` removes the obvious filler
words at the source, but the model occasionally leaves contextual
fillers ("like" when used as filler vs comparison, "you know", "I mean"
mid-thought), false starts, and stuttering repetitions. This service
runs a tight Haiku pass to catch the rest while preserving meaning,
tone, and any technical terms.

Used by the dev-only Voice cleanup feature in admin Settings →
Developer Tools. Invoked once at the end of a recording (on
stopRecording) so there's no mid-recording flicker.

Cost: Haiku at $1/$5 per MTok. A typical 30-second utterance is ~60
input + ~50 output tokens — fractions of a cent.
"""
import logging
from typing import Optional

from app.services.integrations.claude import claude_service
from app.config import prompt_loader
from app.utils import claude_parsing_utils

logger = logging.getLogger(__name__)


class VoicePolishService:
    """Polish a raw voice transcript using Haiku."""

    PROMPT_NAME = "voice_polish"
    # Hard cap on input size — defends against accidental misuse (e.g.
    # a 30-minute transcript). Haiku's context is much larger, but at
    # this point the user is better served by a different tool. The cap
    # also bounds worst-case latency for the on-stop UX.
    MAX_INPUT_CHARS = 6000

    def __init__(self) -> None:
        self._prompt_config: Optional[dict] = None

    def _get_prompt_config(self) -> dict:
        if self._prompt_config is None:
            cfg = prompt_loader.get_prompt_config(self.PROMPT_NAME)
            if cfg is None:
                raise ValueError(
                    f"{self.PROMPT_NAME}_prompt.json not found in data/prompts/"
                )
            self._prompt_config = cfg
        return self._prompt_config

    def polish(
        self,
        text: str,
        project_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> str:
        """Return a cleaned version of the transcript.

        On any failure returns the original text unchanged — voice
        cleanup is a nice-to-have, not load-bearing. The user can
        always still send what they said.
        """
        if not text or not text.strip():
            return text

        # Guard against silly-large inputs (see MAX_INPUT_CHARS doc).
        if len(text) > self.MAX_INPUT_CHARS:
            logger.warning(
                "voice_polish input too large (%d chars), skipping polish",
                len(text),
            )
            return text

        try:
            config = self._get_prompt_config()
            response = claude_service.send_message(
                messages=[{"role": "user", "content": text}],
                system_prompt=config.get("system_prompt", ""),
                model=config.get("model"),
                max_tokens=config.get("max_tokens"),
                temperature=config.get("temperature"),
                project_id=project_id,
                user_id=user_id,
                tags=["voice_polish"],
            )
            cleaned = claude_parsing_utils.extract_text(response).strip()
            # Fall back to original if the model returns nothing (e.g.
            # classified the whole input as filler — the prompt asks
            # for empty string in that case, but for chat input that's
            # almost never what the user wants).
            if not cleaned:
                return text
            return cleaned
        except Exception:
            logger.exception("voice_polish failed; returning original text")
            return text


voice_polish_service = VoicePolishService()
