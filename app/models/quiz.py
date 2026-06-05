"""Quiz models."""
import uuid
import enum
from datetime import datetime
from typing import Any
from sqlalchemy import String, Text, Integer, Float, DateTime, Enum, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class QuizType(str, enum.Enum):
    """Quiz type."""
    MCQ = "mcq"
    OPEN = "open"
    MIXED = "mixed"


class QuizDifficulty(str, enum.Enum):
    """Quiz difficulty level."""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class QuizStatus(str, enum.Enum):
    """Quiz generation status."""
    GENERATING = "generating"
    READY = "ready"
    ERROR = "error"


class QuestionType(str, enum.Enum):
    """Question type."""
    MCQ = "mcq"
    OPEN = "open"


class Quiz(Base):
    """Quiz model."""
    
    __tablename__ = "quizzes"
    
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
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False
    )
    quiz_type: Mapped[QuizType] = mapped_column(
        Enum(QuizType),
        nullable=False
    )
    difficulty: Mapped[QuizDifficulty] = mapped_column(
        Enum(QuizDifficulty),
        nullable=False
    )
    status: Mapped[QuizStatus] = mapped_column(
        Enum(QuizStatus),
        nullable=False,
        default=QuizStatus.GENERATING
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    
    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="quizzes",
        lazy="raise"
    )
    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="quizzes",
        lazy="raise"
    )
    questions: Mapped[list["Question"]] = relationship(
        "Question",
        back_populates="quiz",
        cascade="all, delete-orphan",
        order_by="Question.order_index",
        lazy="raise"
    )
    results: Mapped[list["QuizResult"]] = relationship(
        "QuizResult",
        back_populates="quiz",
        cascade="all, delete-orphan",
        lazy="raise"
    )
    
    def __repr__(self) -> str:
        return f"<Quiz(id={self.id}, title={self.title}, status={self.status})>"


class Question(Base):
    """Question model."""
    
    __tablename__ = "questions"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    quiz_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("quizzes.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    question_type: Mapped[QuestionType] = mapped_column(
        Enum(QuestionType),
        nullable=False
    )
    options: Mapped[list[str] | None] = mapped_column(
        JSON,
        nullable=True
    )
    correct_answer: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    explanation: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    order_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )
    
    # Relationships
    quiz: Mapped["Quiz"] = relationship(
        "Quiz",
        back_populates="questions",
        lazy="raise"
    )
    
    def __repr__(self) -> str:
        return f"<Question(id={self.id}, type={self.question_type})>"


class QuizResult(Base):
    """Quiz result model."""
    
    __tablename__ = "quiz_results"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    quiz_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("quizzes.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    score: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )
    answers: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False
    )
    time_spent: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )
    lacunes: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=False,
        default=list
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    
    # Relationships
    quiz: Mapped["Quiz"] = relationship(
        "Quiz",
        back_populates="results",
        lazy="raise"
    )
    user: Mapped["User"] = relationship(
        "User",
        back_populates="quiz_results",
        lazy="raise"
    )
    
    def __repr__(self) -> str:
        return f"<QuizResult(id={self.id}, score={self.score})>"
