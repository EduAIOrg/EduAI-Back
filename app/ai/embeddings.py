"""Embeddings factory for creating embedding model instances."""
import logging
from typing import Any
from langchain_openai import OpenAIEmbeddings
from langchain_ollama import OllamaEmbeddings

from app.config import settings

logger = logging.getLogger(__name__)


class EmbeddingsFactory:
    """Factory for creating embedding model instances."""
    
    @staticmethod
    def create_embeddings() -> Any:
        """
        Create an embeddings instance based on configuration.
        
        Returns:
            Embeddings instance (OpenAIEmbeddings or OllamaEmbeddings)
        """
        if settings.USE_OLLAMA:
            logger.info(f"Creating Ollama embeddings: {settings.OLLAMA_EMBEDDING_MODEL}")
            return OllamaEmbeddings(
                model=settings.OLLAMA_EMBEDDING_MODEL,
                base_url=settings.OLLAMA_BASE_URL,
            )
        else:
            logger.info("Creating OpenAI embeddings: text-embedding-3-small")
            return OpenAIEmbeddings(
                model="text-embedding-3-small",
                api_key=settings.OPENAI_API_KEY,
            )
