"""Tests for quiz service."""
import pytest
from unittest.mock import Mock, AsyncMock, patch

from app.services.quiz_service import QuizService
from app.models.quiz import Question, QuestionType


class TestQuizService:
    """Test suite for QuizService."""
    
    @pytest.mark.asyncio
    async def test_evaluate_mcq_correct(self):
        """Test MCQ evaluation with correct answer."""
        question = Mock(spec=Question)
        question.id = "test-id"
        question.content = "What is 2+2?"
        question.question_type = QuestionType.MCQ
        question.correct_answer = "A"
        question.explanation = "2+2 equals 4"
        
        result = await QuizService.evaluate_answer(question, "A")
        
        assert result["score"] == 1.0
        assert result["is_correct"] is True
        assert "Correct" in result["feedback"]
    
    @pytest.mark.asyncio
    async def test_evaluate_mcq_incorrect(self):
        """Test MCQ evaluation with incorrect answer."""
        question = Mock(spec=Question)
        question.id = "test-id"
        question.content = "What is 2+2?"
        question.question_type = QuestionType.MCQ
        question.correct_answer = "A"
        question.explanation = "2+2 equals 4"
        
        result = await QuizService.evaluate_answer(question, "B")
        
        assert result["score"] == 0.0
        assert result["is_correct"] is False
        assert "Incorrect" in result["feedback"]
    
    @pytest.mark.asyncio
    async def test_evaluate_mcq_case_insensitive(self):
        """Test MCQ evaluation is case insensitive."""
        question = Mock(spec=Question)
        question.id = "test-id"
        question.content = "What is 2+2?"
        question.question_type = QuestionType.MCQ
        question.correct_answer = "A"
        question.explanation = "2+2 equals 4"
        
        result = await QuizService.evaluate_answer(question, "a")
        
        assert result["score"] == 1.0
        assert result["is_correct"] is True
    
    @pytest.mark.asyncio
    @patch("app.services.quiz_service.LLMFactory.create_evaluation_llm")
    async def test_evaluate_open_question(self, mock_llm_factory):
        """Test open question evaluation using LLM."""
        # Mock LLM response
        mock_llm = AsyncMock()
        mock_response = Mock()
        mock_response.content = '{"score": 0.85, "feedback": "Good answer with minor issues"}'
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_llm_factory.return_value = mock_llm
        
        question = Mock(spec=Question)
        question.id = "test-id"
        question.content = "Explain photosynthesis"
        question.question_type = QuestionType.OPEN
        question.correct_answer = "Process where plants convert light to energy"
        question.explanation = "Photosynthesis explanation"
        
        result = await QuizService.evaluate_answer(
            question,
            "Plants use sunlight to make food"
        )
        
        assert result["score"] == 0.85
        assert result["is_correct"] is True  # >= 0.6
        assert "Good answer" in result["feedback"]
    
    def test_question_type_enum(self):
        """Test QuestionType enum values."""
        assert QuestionType.MCQ.value == "mcq"
        assert QuestionType.OPEN.value == "open"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
