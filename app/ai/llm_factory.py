"""LLM factory for creating language model instances."""
import logging
from typing import Any
from langchain_openai import ChatOpenAI

from app.config import settings

logger = logging.getLogger(__name__)


class LLMFactory:
    """Factory for creating LLM instances."""

    @staticmethod
    def create_llm(streaming: bool = False, temperature: float = 0.7) -> Any:
        """
        Create an OpenAI LLM instance.

        Args:
            streaming: Enable streaming responses
            temperature: Model temperature (0.0-1.0)

        Returns:
            ChatOpenAI instance
        """
        logger.info("Creating OpenAI LLM: gpt-4o-mini")

        return ChatOpenAI(
            model="gpt-4o-mini",
            api_key=settings.OPENAI_API_KEY,
            temperature=temperature,
            streaming=streaming,
        )

    @staticmethod
    def create_chat_llm(streaming: bool = True) -> Any:
        """Chat LLM for conversations."""
        return LLMFactory.create_llm(streaming=streaming, temperature=0.7)

    @staticmethod
    def create_quiz_llm() -> Any:
        """LLM for quiz generation."""
        return LLMFactory.create_llm(streaming=False, temperature=0.5)

    @staticmethod
    def create_evaluation_llm() -> Any:
        """LLM for answer evaluation."""
        return LLMFactory.create_llm(streaming=False, temperature=0.3)

    @staticmethod
    def create_summary_llm() -> Any:
        """LLM for summarization."""
        return LLMFactory.create_llm(streaming=False, temperature=0.5)

    @staticmethod
    def create_translation_llm() -> Any:
        """LLM for translation."""
        return LLMFactory.create_llm(streaming=False, temperature=0.3)