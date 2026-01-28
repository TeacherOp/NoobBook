"""
Audio Service - Transcribes audio files using ElevenLabs Speech-to-Text API.

Educational Note: This service handles audio file transcription using ElevenLabs'
Scribe v1 model (for file-based transcription, not real-time).

Key Features:
- Supports MP3, WAV, M4A, AAC, FLAC formats
- Up to 3GB file size, 10 hours duration
- Speaker diarization (identifies who is speaking)
- Audio event tagging (laughter, applause, music)
- Word-level timestamps
- Auto language detection (100+ languages supported)

Processing Flow:
    Audio file → ElevenLabs API → Transcript text → Split into pages → Save

Supported Languages (sample):
    English (eng), Hindi (hin), Spanish (spa), French (fra), German (deu),
    Japanese (jpn), Korean (kor), Mandarin Chinese (zho), Arabic (ara), etc.
    Full list: https://elevenlabs.io/docs/speech-to-text/overview#supported-languages

Note: This is separate from transcription_service.py which handles real-time
WebSocket transcription for chat voice input.
"""
import os
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime


# Supported language codes for ElevenLabs Speech-to-Text
# Educational Note: Pass None for auto-detection, or one of these codes to force a language
SUPPORTED_LANGUAGES = {
    "auto": None,  # Auto-detect language
    "eng": "English",
    "hin": "Hindi",
    "spa": "Spanish",
    "fra": "French",
    "deu": "German",
    "jpn": "Japanese",
    "kor": "Korean",
    "zho": "Mandarin Chinese",
    "ara": "Arabic",
    "por": "Portuguese",
    "rus": "Russian",
    "ita": "Italian",
    "nld": "Dutch",
    "pol": "Polish",
    "tur": "Turkish",
    "vie": "Vietnamese",
    "tha": "Thai",
    "ind": "Indonesian",
    "msa": "Malay",
}


class AudioService:
    """
    Service class for audio file transcription via ElevenLabs.

    Educational Note: Uses the ElevenLabs Python SDK to transcribe audio files.
    The Scribe v1 model provides high-accuracy transcription with speaker
    diarization and audio event detection.
    """

    # Model for file-based transcription (not realtime)
    TRANSCRIPTION_MODEL = "scribe_v1"

    def __init__(self):
        """Initialize the audio service."""
        self._client = None

    def _get_client(self):
        """
        Get or create the ElevenLabs client.

        Educational Note: We lazy-load the client to avoid import errors
        if the elevenlabs package isn't installed or configured.

        Returns:
            ElevenLabs client instance

        Raises:
            ValueError: If ELEVENLABS_API_KEY is not configured
        """
        if self._client is None:
            api_key = os.getenv('ELEVENLABS_API_KEY')
            if not api_key:
                raise ValueError(
                    "ELEVENLABS_API_KEY not found in environment. "
                    "Please configure it in App Settings."
                )

            from elevenlabs.client import ElevenLabs
            self._client = ElevenLabs(api_key=api_key)

        return self._client

    def transcribe_audio(
        self,
        project_id: str,
        source_id: str,
        audio_path: Path,
        language_code: Optional[str] = None,
        diarize: bool = True,
        tag_audio_events: bool = True
    ) -> Dict[str, Any]:
        """
        Transcribe an audio file using ElevenLabs Scribe v1.

        Educational Note: This method sends the audio file to ElevenLabs
        for transcription. The result includes the full transcript text,
        word-level timestamps, and optionally speaker identification.

        Language Handling:
        - Pass None or "auto" for automatic language detection
        - Pass a valid language code (e.g., "eng", "hin") to force a specific language
        - Empty string is treated as auto-detect

        Args:
            project_id: The project UUID
            source_id: The source UUID
            audio_path: Path to the audio file
            language_code: Language code (e.g., "eng", "hin") or None for auto-detect
            diarize: Enable speaker identification
            tag_audio_events: Enable detection of laughter, applause, etc.

        Returns:
            Dict with success status, transcript, and metadata
        """
        if not audio_path.exists():
            return {
                "success": False,
                "error": f"Audio file not found: {audio_path}"
            }

        try:
            client = self._get_client()

            print(f"Transcribing audio: {audio_path.name}")

            # Normalize language code: empty string or "auto" -> None for auto-detect
            # Educational Note: ElevenLabs expects None (not empty string) for auto-detection
            normalized_language = None
            if language_code and language_code.strip() and language_code.lower() != "auto":
                normalized_language = language_code.strip()
                print(f"Using language code: {normalized_language}")
            else:
                print("Using auto language detection")

            # Read the audio file
            with open(audio_path, "rb") as audio_file:
                # Build API call kwargs conditionally
                # Educational Note: We only pass language_code if explicitly set,
                # otherwise ElevenLabs auto-detects the language
                api_kwargs = {
                    "file": audio_file,
                    "model_id": self.TRANSCRIPTION_MODEL,
                    "diarize": diarize,
                    "tag_audio_events": tag_audio_events,
                    "timestamps_granularity": "word"  # Get word-level timestamps
                }

                # Only add language_code if explicitly specified
                if normalized_language:
                    api_kwargs["language_code"] = normalized_language

                # Call ElevenLabs Speech-to-Text API
                transcription = client.speech_to_text.convert(**api_kwargs)

            # Extract the transcript text
            transcript_text = self._build_transcript_text(transcription, diarize)

            # Get detected language from response
            # Educational Note: ElevenLabs returns the detected (or specified) language code
            detected_language_code = getattr(transcription, 'language_code', None)
            detected_language_name = SUPPORTED_LANGUAGES.get(
                detected_language_code,
                detected_language_code  # Use code as fallback if not in our map
            )

            print(f"Detected language: {detected_language_name} ({detected_language_code})")

            # Build the processed content
            processed_content = self._build_processed_content(
                transcript_text=transcript_text,
                audio_name=audio_path.name,
                transcription=transcription,
                detected_language_code=detected_language_code,
                detected_language_name=detected_language_name,
                diarization_enabled=diarize
            )

            # Calculate token count
            from app.utils.embedding_utils import count_tokens
            token_count = count_tokens(processed_content)

            print(f"Transcript generated: {len(transcript_text)} chars, {token_count} tokens")

            # Return processed content for processor to upload to Supabase Storage
            return {
                "success": True,
                "processed_content": processed_content,
                "character_count": len(transcript_text),
                "token_count": token_count,
                "detected_language_code": detected_language_code,
                "detected_language_name": detected_language_name,
                "model_used": self.TRANSCRIPTION_MODEL,
                "diarization_enabled": diarize,
                "extracted_at": datetime.now().isoformat()
            }

        except ValueError as e:
            # API key not configured
            return {
                "success": False,
                "error": str(e)
            }
        except Exception as e:
            print(f"Error transcribing audio: {e}")
            return {
                "success": False,
                "error": f"Transcription failed: {str(e)}"
            }

    def _build_transcript_text(
        self,
        transcription,
        include_speakers: bool = True
    ) -> str:
        """
        Build transcript text from ElevenLabs response.

        Educational Note: The transcription response contains the full text
        and optionally word-level data with speaker identification. We format
        this into readable text, optionally prefixing speaker changes.

        Args:
            transcription: ElevenLabs transcription response
            include_speakers: Whether to include speaker labels

        Returns:
            Formatted transcript text
        """
        # Get the main text from the transcription
        # The response structure may vary, handle both formats
        if hasattr(transcription, 'text'):
            full_text = transcription.text
        elif isinstance(transcription, dict) and 'text' in transcription:
            full_text = transcription['text']
        else:
            full_text = str(transcription)

        # If diarization is available and enabled, format with speaker labels
        if include_speakers and hasattr(transcription, 'words'):
            formatted_text = self._format_with_speakers(transcription.words)
            if formatted_text:
                return formatted_text

        return full_text

    def _format_with_speakers(self, words) -> Optional[str]:
        """
        Format transcript with speaker labels from word-level data.

        Educational Note: When diarization is enabled, each word has a
        speaker_id. We group consecutive words by speaker and format
        as "Speaker X: [text]" for better readability.

        Args:
            words: List of word objects with speaker_id

        Returns:
            Formatted text with speaker labels, or None if no speaker data
        """
        if not words:
            return None

        # Check if speaker data is available
        first_word = words[0] if words else None
        if not first_word or not hasattr(first_word, 'speaker_id'):
            return None

        lines = []
        current_speaker = None
        current_text = []

        for word in words:
            speaker = getattr(word, 'speaker_id', None)
            # Get word text and strip whitespace
            # Educational Note: ElevenLabs word objects include whitespace in their
            # text field. We strip it and join with single spaces for clean output.
            raw_text = getattr(word, 'text', '') or getattr(word, 'word', '')
            text = raw_text.strip() if raw_text else ''

            if speaker != current_speaker:
                # Save previous speaker's text
                if current_text and current_speaker is not None:
                    speaker_label = f"Speaker {current_speaker}"
                    lines.append(f"{speaker_label}: {' '.join(current_text)}")
                    lines.append("")  # Blank line between speakers

                current_speaker = speaker
                current_text = [text] if text else []
            else:
                if text:
                    current_text.append(text)

        # Don't forget the last speaker's text
        if current_text and current_speaker is not None:
            speaker_label = f"Speaker {current_speaker}"
            lines.append(f"{speaker_label}: {' '.join(current_text)}")

        return "\n".join(lines) if lines else None

    def _build_processed_content(
        self,
        transcript_text: str,
        audio_name: str,
        transcription,
        detected_language_code: Optional[str] = None,
        detected_language_name: Optional[str] = None,
        diarization_enabled: bool = True
    ) -> str:
        """
        Build processed content using centralized build_processed_output.

        Educational Note: We use the centralized build_processed_output function
        to ensure consistent header format across all source types. The audio
        service provides the metadata it knows about (language, model, etc.)
        and build_processed_output handles token counting and page splitting.

        Args:
            transcript_text: The full transcript text
            audio_name: Original audio filename
            transcription: ElevenLabs transcription response for metadata
            detected_language_code: Language code (e.g., "eng") from ElevenLabs
            detected_language_name: Human-readable language name (e.g., "English")
            diarization_enabled: Whether speaker diarization was enabled

        Returns:
            Formatted content with standardized header and AUDIO PAGE markers
        """
        from app.utils.text import build_processed_output
        from app.utils.embedding_utils import count_tokens

        # Audio transcripts don't have logical page boundaries
        # Pass entire transcript as single page, let token-based chunking handle splits
        pages = [transcript_text]

        # Build language display string
        language = ""
        if detected_language_code:
            language = f"{detected_language_name} ({detected_language_code})" if detected_language_name else detected_language_code

        # Calculate token count for the full transcript
        token_count = count_tokens(transcript_text)

        # Build metadata dict with all keys audio service can provide
        # Educational Note: duration is not available from ElevenLabs transcription API
        metadata = {
            "model_used": self.TRANSCRIPTION_MODEL,
            "language": language,
            "duration": "",  # Not available from ElevenLabs transcription response
            "diarization_enabled": diarization_enabled,
            "character_count": len(transcript_text),
            "token_count": token_count
        }

        # Use centralized build_processed_output for consistent format
        return build_processed_output(
            pages=pages,
            source_type="AUDIO",
            source_name=audio_name,
            metadata=metadata
        )

    def is_configured(self) -> bool:
        """
        Check if ElevenLabs API key is configured for transcription.

        Returns:
            True if API key is set, False otherwise
        """
        return bool(os.getenv('ELEVENLABS_API_KEY'))


# Singleton instance
audio_service = AudioService()
