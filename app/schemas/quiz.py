"""Quiz schemas."""
from datetime import datetime
from uuid import UUID
from typing import Any
from pydantic import BaseModel, Field

from app.models.quiz import QuizType, QuizDifficulty, QuizStatus, QuestionType


class QuizCreate(BaseModel):
    """Quiz creation request."""
    document_id: UUID = Field(..., description="Document ID to generate quiz from")
    quiz_type: QuizType = Field(..., description="Quiz type (mcq/open/mixed)")
    difficulty: QuizDifficulty = Field(..., description="Difficulty level")
    num_questions: int = Field(default=10, ge=1, le=50, description="Number of questions")
    title: str = Field(default="Quiz", description="Quiz title")


class QuestionResponse(BaseModel):
    """Question response model."""
    id: UUID = Field(..., description="Question ID")
    quiz_id: UUID = Field(..., description="Quiz ID")
    content: str = Field(..., description="Question content")
    question_type: QuestionType = Field(..., description="Question type")
    options: list[str] | None = Field(None, description="MCQ options (4 choices)")
    order_index: int = Field(..., description="Question order")
    
    model_config = {
        "from_attributes": True
    }


class QuestionWithAnswer(BaseModel):
    """Question with correct answer (for results)."""
    id: UUID = Field(..., description="Question ID")
    content: str = Field(..., description="Question content")
    question_type: QuestionType = Field(..., description="Question type")
    options: list[str] | None = Field(None, description="MCQ options")
    correct_answer: str = Field(..., description="Correct answer")
    explanation: str = Field(..., description="Answer explanation")
    order_index: int = Field(..., description="Question order")
    
    model_config = {
        "from_attributes": True
    }


class QuizResponse(BaseModel):
    """Quiz response model."""
    id: UUID = Field(..., description="Quiz ID")
    user_id: UUID = Field(..., description="Owner user ID")
    document_id: UUID = Field(..., description="Associated document ID")
    title: str = Field(..., description="Quiz title")
    quiz_type: QuizType = Field(..., description="Quiz type")
    difficulty: QuizDifficulty = Field(..., description="Difficulty level")
    status: QuizStatus = Field(..., description="Generation status")
    created_at: datetime = Field(..., description="Creation timestamp")
    questions: list[QuestionResponse] = Field(default_factory=list, description="Quiz questions")
    
    model_config = {
        "from_attributes": True
    }


class QuizStatusResponse(BaseModel):
    """Quiz status response."""
    status: QuizStatus = Field(..., description="Generation status")
    progress_message: str = Field(..., description="Human-readable progress message")


class AnswerSubmit(BaseModel):
    """Single answer submission."""
    question_id: UUID = Field(..., description="Question ID")
    answer: str = Field(..., description="User's answer")


class QuizSubmit(BaseModel):
    """Quiz submission request."""
    answers: list[AnswerSubmit] = Field(..., description="List of answers")
    time_spent: int = Field(..., ge=0, description="Time spent in seconds")


class AnswerFeedback(BaseModel):
    """Feedback for a single answer."""
    question_id: UUID = Field(..., description="Question ID")
    is_correct: bool = Field(..., description="Whether answer is correct")
    score: float = Field(..., ge=0.0, le=1.0, description="Score for this question (0.0-1.0)")
    user_answer: str = Field(..., description="User's answer")
    correct_answer: str = Field(..., description="Correct answer")
    feedback: str = Field(..., description="Detailed feedback")


class LacuneItem(BaseModel):
    """Learning gap item."""
    notion: str = Field(..., description="Concept/notion name")
    level: str = Field(..., description="Mastery level (weak/medium/strong)")
    last_seen: datetime = Field(..., description="Last time this gap was identified")
    recommendations: list[str] = Field(default_factory=list, description="Study recommendations")


class QuizResultResponse(BaseModel):
    """Quiz result response."""
    id: UUID = Field(..., description="Result ID")
    quiz_id: UUID = Field(..., description="Quiz ID")
    user_id: UUID = Field(..., description="User ID")
    score: float = Field(..., ge=0.0, le=1.0, description="Overall score (0.0-1.0)")
    time_spent: int = Field(..., description="Time spent in seconds")
    created_at: datetime = Field(..., description="Submission timestamp")
    answer_feedback: list[AnswerFeedback] = Field(..., description="Feedback for each answer")
    lacunes: list[LacuneItem] = Field(default_factory=list, description="Identified learning gaps")
    
    model_config = {
        "from_attributes": True
    }


class QuizListItem(BaseModel):
    """Quiz list item."""
    id: UUID = Field(..., description="Quiz ID")
    title: str = Field(..., description="Quiz title")
    quiz_type: QuizType = Field(..., description="Quiz type")
    difficulty: QuizDifficulty = Field(..., description="Difficulty level")
    status: QuizStatus = Field(..., description="Generation status")
    created_at: datetime = Field(..., description="Creation timestamp")
    question_count: int = Field(default=0, description="Number of questions")
    last_score: float | None = Field(None, description="Last score if quiz was taken")
    
    model_config = {
        "from_attributes": True
    }
