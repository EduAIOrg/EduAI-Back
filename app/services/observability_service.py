"""Service for tracking AI metrics (Observability)."""
import logging
import time
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.observability import LLMRequest, EmbeddingRequest, RerankingRequest

logger = logging.getLogger(__name__)


class AIObservabilityService:
    """Service to log and track performance and utilization of LLM, Embedding, and Reranking operations."""
    
    @staticmethod
    async def log_llm_request(
        db: AsyncSession,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: float,
        status: str,
        user_id: UUID | None = None,
        error_message: str | None = None
    ) -> LLMRequest:
        """Log an LLM request metrics."""
        try:
            total_tokens = prompt_tokens + completion_tokens
            
            # Local hosting cost is 0, but we log tokens and latency
            request_log = LLMRequest(
                user_id=user_id,
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                latency_ms=latency_ms,
                cost=0.0,
                status=status,
                error_message=error_message
            )
            db.add(request_log)
            await db.commit()
            return request_log
        except Exception as e:
            logger.error(f"Failed to log LLM request: {e}")
            await db.rollback()
            
    @staticmethod
    async def log_embedding_request(
        db: AsyncSession,
        model: str,
        input_texts_count: int,
        total_tokens: int,
        latency_ms: float,
        status: str,
        user_id: UUID | None = None
    ) -> EmbeddingRequest:
        """Log an embedding generation request metrics."""
        try:
            request_log = EmbeddingRequest(
                user_id=user_id,
                model=model,
                input_texts_count=input_texts_count,
                total_tokens=total_tokens,
                latency_ms=latency_ms,
                cost=0.0,
                status=status
            )
            db.add(request_log)
            await db.commit()
            return request_log
        except Exception as e:
            logger.error(f"Failed to log embedding request: {e}")
            await db.rollback()

    @staticmethod
    async def log_reranking_request(
        db: AsyncSession,
        model: str,
        documents_count: int,
        latency_ms: float,
        status: str,
        user_id: UUID | None = None
    ) -> RerankingRequest:
        """Log a document reranking request metrics."""
        try:
            request_log = RerankingRequest(
                user_id=user_id,
                model=model,
                documents_count=documents_count,
                latency_ms=latency_ms,
                cost=0.0,
                status=status
            )
            db.add(request_log)
            await db.commit()
            return request_log
        except Exception as e:
            logger.error(f"Failed to log reranking request: {e}")
            await db.rollback()
