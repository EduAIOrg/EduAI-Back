"""LLM factory for creating language model instances."""
import logging
from typing import Any
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama

from app.config import settings

logger = logging.getLogger(__name__)


class LLMFactory:
    """Factory for creating LLM instances."""
    
    @staticmethod
    def create_llm(streaming: bool = False, temperature: float = 0.7) -> Any:
        """
        Create an LLM instance based on configuration.
        
        Args:
            streaming: Enable streaming responses
            temperature: Model temperature (0.0-1.0)
            
        Returns:
            LLM instance (ChatOpenAI or ChatOllama)
        """
        if settings.USE_OLLAMA:
            logger.info(f"Creating Ollama LLM: {settings.OLLAMA_MODEL}")
            return ChatOllama(
                model=settings.OLLAMA_MODEL,
                base_url=settings.OLLAMA_BASE_URL,
                temperature=temperature,
            )
        else:
            logger.info("Creating OpenAI LLM: gpt-4o-mini")
            return ChatOpenAI(
                model="gpt-4o-mini",
                api_key=settings.OPENAI_API_KEY,
                temperature=temperature,
                streaming=streaming,
            )
    
    @staticmethod
    def create_chat_llm(streaming: bool = True) -> Any:
        """
        Create an LLM for chat interactions.
        
        Args:
            streaming: Enable streaming responses
            
        Returns:
            LLM instance configured for chat
        """
        return LLMFactory.create_llm(streaming=streaming, temperature=0.7)
    
    @staticmethod
    def create_quiz_llm() -> Any:
        """
        Create an LLM for quiz generation.
        
        Returns:
            LLM instance configured for quiz generation
        """
        return LLMFactory.create_llm(streaming=False, temperature=0.5)
    
    @staticmethod
    def create_evaluation_llm() -> Any:
        """
        Create an LLM for answer evaluation.
        
        Returns:
            LLM instance configured for evaluation
        """
        return LLMFactory.create_llm(streaming=False, temperature=0.3)
    
    @staticmethod
    def create_summary_llm() -> Any:
        """
        Create an LLM for document summarization.
        
        Returns:
            LLM instance configured for summarization
        """
        return LLMFactory.create_llm(streaming=False, temperature=0.5)
    
    @staticmethod
    def create_translation_llm() -> Any:
        """
        Create an LLM for translation.
        
        Returns:
            LLM instance configured for translation
        """
        return LLMFactory.create_llm(streaming=False, temperature=0.3)
