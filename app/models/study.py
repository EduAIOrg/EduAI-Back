"""Study and SaaS learning models."""
import uuid
from datetime import datetime
from typing import Any
from sqlalchemy import String, Text, Integer, Float, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class Flashcard(Base):
    """Flashcard model for Leitner space-repetition review system."""
    
    __tablename__ = "flashcards"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    question: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    answer: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    box: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False
    )
    next_review: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    
    # Relationships
    user: Mapped["User"] = relationship("User")
    document: Mapped["Document"] = relationship("Document")


class StudentQuizAnswer(Base):
    """Detailed logs of student answers to each quiz question."""
    
    __tablename__ = "student_quiz_answers"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    quiz_result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("quiz_results.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    user_answer: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    is_correct: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False
    )
    score: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )
    feedback: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    
    # Relationships
    user: Mapped["User"] = relationship("User")
    quiz_result: Mapped["QuizResult"] = relationship("QuizResult")
    question: Mapped["Question"] = relationship("Question")
