"""Voice service for transcription and synthesis."""
import logging
from pathlib import Path
from typing import AsyncGenerator
import httpx
from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)


class VoiceService:
    """Service for voice operations."""
    
    def __init__(self):
        """Initialize OpenAI client."""
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    
    async def transcribe_audio(self, audio_file_path: str) -> str:
        """
        Transcribe audio file using OpenAI Whisper.
        
        Args:
            audio_file_path: Path to audio file
            
        Returns:
            str: Transcribed text
        """
        try:
            logger.info(f"Transcribing audio file: {audio_file_path}")
            
            with open(audio_file_path, "rb") as audio_file:
                transcript = await self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="fr"  # French by default
                )
            
            transcribed_text = transcript.text
            logger.info(f"Transcription completed: {len(transcribed_text)} characters")
            
            return transcribed_text
            
        except Exception as e:
            logger.error(f"Error transcribing audio: {e}")
            raise
    
    async def synthesize_speech(
        self,
        text: str,
        voice: str = "alloy",
        model: str = "tts-1"
    ) -> AsyncGenerator[bytes, None]:
        """
        Synthesize speech from text using OpenAI TTS.
        
        Args:
            text: Text to synthesize
            voice: Voice to use (alloy, echo, fable, onyx, nova, shimmer)
            model: TTS model (tts-1 or tts-1-hd)
            
        Yields:
            bytes: Audio chunks
        """
        try:
            logger.info(f"Synthesizing speech: {len(text)} characters")
            
            response = await self.client.audio.speech.create(
                model=model,
                voice=voice,
                input=text
            )
            
            # Stream audio chunks
            async for chunk in response.iter_bytes(chunk_size=4096):
                yield chunk
            
            logger.info("Speech synthesis completed")
            
        except Exception as e:
            logger.error(f"Error synthesizing speech: {e}")
            raise


# Global voice service instance
voice_service = VoiceService()
