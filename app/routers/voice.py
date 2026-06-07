"""Voice router for transcription and synthesis."""
import logging
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from pydantic import BaseModel

from app.dependencies import get_current_user
from app.models.user import User
from app.services.voice_service import voice_service
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["Voice"])


class TranscribeResponse(BaseModel):
    """Transcription response."""
    transcript: str





from app.dependencies import get_db
from sqlalchemy.ext.asyncio import AsyncSession


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(
    audio: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> TranscribeResponse:
    """
    Transcribe audio file using Whisper.
    
    Args:
        audio: Audio file (webm, wav, mp3, etc.)
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        TranscribeResponse: Transcribed text
    """
    try:
        from app.services.quota_service import QuotaService
        if not await QuotaService.check_quota(db, current_user, "transcription"):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Quota journalier de transcription audio dépassé pour votre forfait."
            )
        # Validate file type
        allowed_types = [
            "audio/webm",
            "audio/wav",
            "audio/mpeg",
            "audio/mp4",
            "audio/ogg"
        ]
        
        if audio.content_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported audio format: {audio.content_type}"
            )
        
        # Save temporary file
        temp_dir = Path(settings.UPLOADS_DIR) / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        file_id = uuid.uuid4()
        file_extension = Path(audio.filename).suffix or ".webm"
        temp_file_path = temp_dir / f"{file_id}{file_extension}"
        
        # Write audio file
        content = await audio.read()
        with open(temp_file_path, "wb") as f:
            f.write(content)
        
        try:
            # Transcribe
            transcript = await voice_service.transcribe_audio(str(temp_file_path))
            
            # Increment quota usage
            await QuotaService.increment_usage(db, current_user.id, "transcription")
            
            logger.info(f"Audio transcribed: {len(transcript)} characters")
            
            return TranscribeResponse(transcript=transcript)
            
        finally:
            # Clean up temp file
            if temp_file_path.exists():
                temp_file_path.unlink()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error transcribing audio: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to transcribe audio"
        )


@router.get("/transcribe/test")
async def test_transcribe_connectivity(
    current_user: User = Depends(get_current_user)
):
    """
    Test if the Whisper transcription model on Hugging Face is reachable.
    """
    try:
        status_info = await voice_service.test_transcription_model_status()
        return status_info
    except Exception as e:
        logger.error(f"Error checking Whisper transcription model connectivity: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to test Whisper transcription model connectivity: {str(e)}"
        )

