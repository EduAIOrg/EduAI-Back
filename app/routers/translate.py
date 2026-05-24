"""Translation router."""
import logging
from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.translate import TranslateRequest, TranslateResponse
from app.services.translate_service import TranslateService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/translate", tags=["Translation"])


@router.post("/", response_model=TranslateResponse)
async def translate_text(
    request: TranslateRequest,
    current_user: User = Depends(get_current_user)
) -> TranslateResponse:
    """
    Translate text between French and English.
    
    Args:
        request: Translation request
        current_user: Current authenticated user
        
    Returns:
        TranslateResponse: Translated text
    """
    try:
        translated_text = await TranslateService.translate_text(
            text=request.text,
            source_lang=request.source_lang,
            target_lang=request.target_lang,
            preserve_pedagogical_context=request.preserve_pedagogical_context
        )
        
        logger.info(f"Translated text from {request.source_lang} to {request.target_lang}")
        
        return TranslateResponse(
            translated_text=translated_text,
            source_lang=request.source_lang,
            target_lang=request.target_lang
        )
        
    except Exception as e:
        logger.error(f"Error translating text: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to translate text"
        )
