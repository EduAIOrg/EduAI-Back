"""Voice service for transcription and synthesis."""
import logging
from pathlib import Path
from typing import AsyncGenerator
import httpx
from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)


class VoiceService:
    """Service for local voice operations (Whisper and XTTS-v2)."""
    
    def __init__(self):
        """Initialize local Whisper AsyncOpenAI client."""
        self.whisper_client = AsyncOpenAI(
            base_url=settings.WHISPER_API_URL,
            api_key="none"
        )
    
    async def transcribe_audio(self, audio_file_path: str) -> str:
        """
        Transcribe audio file using local Faster-Whisper.
        
        Args:
            audio_file_path: Path to audio file
            
        Returns:
            str: Transcribed text
        """
        try:
            logger.info(f"Transcribing audio file locally: {audio_file_path}")
            
            with open(audio_file_path, "rb") as audio_file:
                transcript = await self.whisper_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="fr"  # French by default
                )
            
            transcribed_text = transcript.text
            logger.info(f"Local transcription completed: {len(transcribed_text)} characters")
            
            return transcribed_text
            
        except Exception as e:
            logger.error(f"Error transcribing audio with Whisper local: {e}")
            raise
    
    async def synthesize_speech(
        self,
        text: str,
        voice: str = "alloy",
        model: str = "tts-1"
    ) -> AsyncGenerator[bytes, None]:
        """
        Synthesize speech from text using local XTTS-v2 API.
        
        Args:
            text: Text to synthesize
            voice: Voice key or speaker reference
            model: Model name
            
        Yields:
            bytes: Audio chunks
        """
        try:
            logger.info(f"Synthesizing speech via XTTS-v2 local API: {len(text)} characters")
            
            # XTTS-v2 standard endpoint: POST /tts returning raw audio stream
            # Let's request the endpoint asynchronously
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{settings.XTTS_API_URL}/tts",
                    json={
                        "text": text,
                        "speaker_id": voice if voice != "alloy" else "Female Speaker 1",
                        "language": "fr"
                    }
                )
                response.raise_for_status()
                
                # Stream the response content in chunks
                async for chunk in response.aiter_bytes(chunk_size=4096):
                    yield chunk
            
            logger.info("Local XTTS-v2 speech synthesis completed")
            
        except Exception as e:
            logger.error(f"Error synthesizing speech with XTTS-v2: {e}")
            # Fallback to general silent bytes or a simple text-to-speech error response if needed
            raise


# Global voice service instance
voice_service = VoiceService()
