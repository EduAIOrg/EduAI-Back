"""Tests for quiz router."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime

from fastapi import HTTPException
from app.routers.quiz import list_quizzes, get_quiz
from app.models.user import User
from app.models.quiz import Quiz, Question, QuizResult, QuizStatus, QuizType, QuizDifficulty


@pytest.mark.asyncio
async def test_list_quizzes():
    # Mock db and user
    mock_db = AsyncMock()
    mock_user = MagicMock(spec=User)
    mock_user.id = uuid4()
    
    # Mock Quiz object with questions preloaded
    mock_quiz = MagicMock(spec=Quiz)
    mock_quiz.id = uuid4()
    mock_quiz.title = "Mock Quiz"
    mock_quiz.quiz_type = QuizType.MCQ
    mock_quiz.difficulty = QuizDifficulty.EASY
    mock_quiz.status = QuizStatus.READY
    mock_quiz.created_at = datetime.utcnow()
    
    # Preloaded relationship list
    mock_question = MagicMock(spec=Question)
    mock_quiz.questions = [mock_question]
    
    mock_result_db = MagicMock()
    mock_result_db.scalars.return_value.all.return_value = [mock_quiz]
    
    # Mock db.execute for:
    # 1. select(Quiz)...
    # 2. select(QuizResult)... (last score)
    mock_score = MagicMock(spec=QuizResult)
    mock_score.score = 0.9
    mock_score_db = MagicMock()
    mock_score_db.scalar_one_or_none.return_value = mock_score
    
    mock_db.execute.side_effect = [
        mock_result_db,  # quizzes query
        mock_score_db    # last score query
    ]
    
    response = await list_quizzes(current_user=mock_user, db=mock_db)
    
    assert len(response) == 1
    assert response[0].title == "Mock Quiz"
    assert response[0].question_count == 1
    assert response[0].last_score == 0.9


@pytest.mark.asyncio
async def test_get_quiz():
    # Mock db and user
    mock_db = AsyncMock()
    mock_user = MagicMock(spec=User)
    mock_user.id = uuid4()
    
    # Mock Quiz object with questions
    mock_quiz = MagicMock(spec=Quiz)
    mock_quiz.id = uuid4()
    mock_quiz.user_id = mock_user.id
    mock_quiz.document_id = uuid4()
    mock_quiz.title = "Mock Quiz"
    mock_quiz.quiz_type = QuizType.MCQ
    mock_quiz.difficulty = QuizDifficulty.EASY
    mock_quiz.status = QuizStatus.READY
    mock_quiz.created_at = datetime.utcnow()
    
    # Questions relation
    mock_question = Question(
        id=uuid4(),
        quiz_id=mock_quiz.id,
        content="Is this a question?",
        question_type=QuizType.MCQ,
        options=["Yes", "No"],
        correct_answer="Yes",
        explanation="Self explanatory",
        order_index=0
    )
    mock_quiz.questions = [mock_question]
    
    mock_result_db = MagicMock()
    mock_result_db.scalar_one_or_none.return_value = mock_quiz
    
    mock_db.execute.return_value = mock_result_db
    
    response = await get_quiz(quiz_id=mock_quiz.id, current_user=mock_user, db=mock_db)
    
    assert response.title == "Mock Quiz"
    assert len(response.questions) == 1
    assert response.questions[0].content == "Is this a question?"
