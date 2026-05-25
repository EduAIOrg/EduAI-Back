"""Embeddings factory for creating embedding model instances."""
import logging
from typing import Any
from langchain_openai import OpenAIEmbeddings

from app.config import settings

logger = logging.getLogger(__name__)


class EmbeddingsFactory:
    """Factory for creating embedding model instances."""

    @staticmethod
    def create_embeddings() -> Any:
        """
        Create OpenAI embeddings instance.
        """
        logger.info("Creating OpenAI embeddings: text-embedding-3-small")

        return OpenAIEmbeddings(
            model="text-embedding-3-small",
            api_key=settings.OPENAI_API_KEY,
        )