"""Voice service for transcription and synthesis using Hugging Face Router."""
import logging
import time
import asyncio
import mimetypes
from pathlib import Path
from typing import AsyncGenerator
import httpx
from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)


class VoiceService:
    """Service for voice operations (Whisper via Hugging Face Router and future-proof XTTS-v2)."""
    
    def __init__(self):
        """Initialize service."""
        # Initialize client only if custom OpenAI-compatible endpoint is specified
        self.openai_client = None
        if settings.WHISPER_API_URL:
            self.openai_client = AsyncOpenAI(
                base_url=settings.WHISPER_API_URL,
                api_key="none"
            )
            
    async def transcribe_audio(self, audio_file_path: str) -> str:
        """
        Transcribe audio file.
        
        Uses Hugging Face Router by default. Falls back to OpenAI-compatible
        custom endpoint if settings.WHISPER_API_URL is configured.
        
        Args:
            audio_file_path: Path to local audio file
            
        Returns:
            str: Transcribed text
        """
        path = Path(audio_file_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found at: {audio_file_path}")
            
        return await self._transcribe_audio_internal(audio_file_path)

    async def _transcribe_audio_internal(self, audio_file_path: str) -> str:
        """Helper to run the core transcription logic (open connection, send POST, handle response)."""
        path = Path(audio_file_path)
        file_size = path.stat().st_size
        suffix = path.suffix.lower()
        
        # 1. Custom Endpoint Fallback
        if settings.WHISPER_API_URL:
            logger.info(f"Using custom OpenAI-compatible Whisper base URL: {settings.WHISPER_API_URL}")
            return await self._transcribe_audio_openai_compatible(audio_file_path)
            
        # 2. Hugging Face Router API
        url = f"https://router.huggingface.co/hf-inference/models/{settings.HF_WHISPER_MODEL}"
        
        # Determine automatically the Content-Type according to the extension
        mime_mapping = {
            ".webm": "audio/webm",
            ".wav": "audio/wav",
            ".ogg": "audio/ogg",
            ".mp3": "audio/mpeg",
            ".m4a": "audio/m4a"
        }
        mime_type = mime_mapping.get(suffix)
        
        # Never send video/webm
        if not mime_type or mime_type == "video/webm":
            mime_type = "audio/webm"
            
        logger.info(
            "AUDIO FILE INFO | size=%d bytes | extension=%s | content_type=%s | url=%s",
            file_size, suffix, mime_type, url
        )
            
        logger.info(f"Sending audio file with Content-Type={mime_type}")
        
        headers = {
            "Content-Type": mime_type
        }
        if settings.HF_TOKEN:
            # Mask token in logs for security
            masked_token = settings.HF_TOKEN[:4] + "..." + settings.HF_TOKEN[-4:] if len(settings.HF_TOKEN) > 8 else "..."
            logger.info(f"Authenticating with Hugging Face Token: {masked_token}")
            headers["Authorization"] = f"Bearer {settings.HF_TOKEN}"
        else:
            logger.warning("HF_TOKEN is empty. Requests to Hugging Face Router may fail or be rate-limited.")
            
        with open(audio_file_path, "rb") as f:
            audio_data = f.read()
            
        retries = settings.HF_VOICE_RETRIES
        timeout = settings.HF_VOICE_TIMEOUT
        
        for attempt in range(1, retries + 1):
            start_time = time.time()
            try:
                logger.info(f"Sending request to Hugging Face Router Whisper API (attempt {attempt}/{retries})...")
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        url,
                        headers=headers,
                        content=audio_data
                    )
                
                elapsed = time.time() - start_time
                logger.info(f"HF Router Whisper API response received in {elapsed:.2f}s (status code: {response.status_code})")
                
                # Check for 503 loading error
                if response.status_code == 503:
                    try:
                        res_json = response.json()
                        estimated_time = res_json.get("estimated_time", 10.0)
                        error_msg = res_json.get("error", "Model is loading")
                    except Exception:
                        estimated_time = 10.0
                        error_msg = "Model is currently loading (503)"
                        
                    logger.warning(
                        f"HF Model is loading: '{error_msg}'. "
                        f"Estimated time: {estimated_time}s. Retrying in {min(estimated_time, 15.0)}s..."
                    )
                    await asyncio.sleep(min(estimated_time, 15.0))
                    continue
                    
                response.raise_for_status()
                
                result = response.json()
                logger.info(f"HF Whisper raw response: {result}")
                
                transcript = ""
                
                # Extract text depending on exact Hugging Face response format
                if isinstance(result, dict):
                    transcript = result.get("text", "")
                    if not transcript and "chunks" in result:
                        transcript = " ".join(chunk.get("text", "") for chunk in result["chunks"] if isinstance(chunk, dict))
                elif isinstance(result, list) and len(result) > 0:
                    if isinstance(result[0], dict):
                        transcript = result[0].get("text", "")
                        if not transcript and "chunks" in result[0]:
                            transcript = " ".join(chunk.get("text", "") for chunk in result[0]["chunks"] if isinstance(chunk, dict))
                    elif isinstance(result[0], str):
                        transcript = " ".join(result)
                        
                logger.info(f"HF Router Transcription succeeded: {len(transcript)} characters")
                return transcript
                
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTPStatusError during HF Router Whisper transcription: {e.response.status_code} - {e.response.text}")
                if attempt == retries:
                    raise
            except httpx.RequestError as e:
                logger.error(f"Network error during HF Router Whisper transcription: {e}")
                if attempt == retries:
                    raise
            except Exception as e:
                logger.error(f"Unexpected error during HF Router Whisper transcription: {e}")
                if attempt == retries:
                    raise
                    
            sleep_dur = 2 ** attempt
            logger.info(f"Retrying in {sleep_dur}s...")
            await asyncio.sleep(sleep_dur)
            
        raise Exception("Failed to transcribe audio after all retry attempts.")
        
    async def _transcribe_audio_openai_compatible(self, audio_file_path: str) -> str:
        """Transcribe audio using AsyncOpenAI compatible client."""
        if not self.openai_client:
            self.openai_client = AsyncOpenAI(
                base_url=settings.WHISPER_API_URL,
                api_key="none"
            )
            
        with open(audio_file_path, "rb") as audio_file:
            transcript = await self.openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="fr"
            )
        return transcript.text

    async def test_transcription_model_status(self) -> dict:
        """
        Test if the transcription model is reachable on Hugging Face Router.
        
        Returns:
            dict: Status details
        """
        if settings.WHISPER_API_URL:
            return {
                "status": "custom_endpoint",
                "message": f"Using custom Whisper base URL: {settings.WHISPER_API_URL}",
                "model": "unknown"
            }
            
        url = f"https://router.huggingface.co/hf-inference/models/{settings.HF_WHISPER_MODEL}"
        headers = {}
        if settings.HF_TOKEN:
            headers["Authorization"] = f"Bearer {settings.HF_TOKEN}"
            
        logger.info(f"Testing Whisper model connectivity via HF Router: {url}")
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                hub_url = f"https://huggingface.co/api/models/{settings.HF_WHISPER_MODEL}"
                response = await client.get(hub_url, headers=headers)
                
            if response.status_code == 200:
                model_data = response.json()
                async with httpx.AsyncClient(timeout=5.0) as client:
                    inf_response = await client.post(url, headers=headers, content=b"")
                    
                inf_status = "ready"
                if inf_response.status_code == 503:
                    inf_status = "loading"
                elif inf_response.status_code == 400:
                    inf_status = "ready"  # normal for empty body POST to Whisper
                elif inf_response.status_code == 401:
                    inf_status = "unauthorized"
                elif inf_response.status_code != 200:
                    inf_status = f"error_{inf_response.status_code}"
                
                return {
                    "status": "ok",
                    "inference_status": inf_status,
                    "model_id": model_data.get("id"),
                    "downloads": model_data.get("downloads", 0),
                    "tags": model_data.get("tags", []),
                    "message": "Model is reachable via Hugging Face Router."
                }
            else:
                return {
                    "status": "error",
                    "message": f"Hugging Face Hub API returned status code {response.status_code}: {response.text}"
                }
        except Exception as e:
            logger.error(f"Failed to check Whisper model connectivity via HF Router: {e}")
            return {
                "status": "error",
                "message": f"Connection to Hugging Face Router failed: {str(e)}"
            }


# Global voice service instance
voice_service = VoiceService()
