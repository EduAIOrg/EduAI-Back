"""Translation service."""
import logging
from app.ai.llm_factory import LLMFactory
from app.ai.prompts import get_translation_prompt

logger = logging.getLogger(__name__)


class TranslateService:
    """Service for text translation."""
    
    @staticmethod
    async def translate_text(
        text: str,
        source_lang: str,
        target_lang: str,
        preserve_pedagogical_context: bool = True
    ) -> str:
        """
        Translate text between French and English.
        
        Args:
            text: Text to translate
            source_lang: Source language code (fr/en)
            target_lang: Target language code (fr/en)
            preserve_pedagogical_context: Preserve pedagogical terminology
            
        Returns:
            str: Translated text
        """
        try:
            if source_lang == target_lang:
                logger.info("Source and target languages are the same, returning original text")
                return text
            
            # Create LLM and prompt
            llm = LLMFactory.create_translation_llm()
            prompt = get_translation_prompt()
            
            # Prepare context preservation instruction
            preserve_context = (
                "Préserve la terminologie pédagogique et le contexte académique."
                if preserve_pedagogical_context
                else "Traduis de manière naturelle."
            )
            
            # Translate
            chain = prompt | llm
            response = await chain.ainvoke({
                "text": text,
                "source_lang": source_lang,
                "target_lang": target_lang,
                "preserve_context": preserve_context
            })
            
            translated_text = response.content.strip()
            
            logger.info(f"Translated text from {source_lang} to {target_lang}")
            return translated_text
            
        except Exception as e:
            logger.error(f"Error translating text: {e}")
            raise
