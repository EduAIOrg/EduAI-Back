"""Observability models for AI requests logging and costing."""
import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class LLMRequest(Base):
    """Model to log all LLM requests."""
    
    __tablename__ = "llm_requests"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    model: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    prompt_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )
    completion_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )
    total_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )
    latency_ms: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )
    cost: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0
    )
    status: Mapped[str] = mapped_column(
        String(50),  # "success" or "error"
        nullable=False
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )


class EmbeddingRequest(Base):
    """Model to log all Embedding requests."""
    
    __tablename__ = "embedding_requests"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    model: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    input_texts_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1
    )
    total_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )
    latency_ms: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )
    cost: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0
    )
    status: Mapped[str] = mapped_column(
        String(50),  # "success" or "error"
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )


class RerankingRequest(Base):
    """Model to log all Reranking requests."""
    
    __tablename__ = "reranking_requests"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    model: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    documents_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )
    latency_ms: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )
    cost: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0
    )
    status: Mapped[str] = mapped_column(
        String(50),  # "success" or "error"
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
