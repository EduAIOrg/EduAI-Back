"""Translation schemas."""
from pydantic import BaseModel, Field


class TranslateRequest(BaseModel):
    """Translation request."""
    text: str = Field(..., min_length=1, description="Text to translate")
    source_lang: str = Field(..., pattern="^(fr|en)$", description="Source language (fr/en)")
    target_lang: str = Field(..., pattern="^(fr|en)$", description="Target language (fr/en)")
    preserve_pedagogical_context: bool = Field(
        default=True,
        description="Preserve pedagogical terminology and context"
    )


class TranslateResponse(BaseModel):
    """Translation response."""
    translated_text: str = Field(..., description="Translated text")
    source_lang: str = Field(..., description="Source language")
    target_lang: str = Field(..., description="Target language")
