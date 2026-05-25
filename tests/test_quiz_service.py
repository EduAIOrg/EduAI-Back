import pytest
from unittest.mock import Mock, AsyncMock, MagicMock, patch

from app.services.quiz_service import QuizService
from app.models.quiz import Question, QuestionType


@pytest.mark.asyncio
@patch("app.services.quiz_service.get_answer_evaluation_prompt")
@patch("app.services.quiz_service.LLMFactory.create_evaluation_llm")
async def test_evaluate_open_question(mock_llm_factory, mock_prompt):
    """Test open question evaluation using LLM."""

    # Mock response
    mock_response = Mock()
    mock_response.content = (
        '{"score": 0.85, "feedback": "Good answer with minor issues"}'
    )

    # Mock chain
    mock_chain = Mock()
    mock_chain.ainvoke = AsyncMock(return_value=mock_response)

    # Mock prompt object
    mock_prompt_instance = MagicMock()
    mock_prompt_instance.__or__.return_value = mock_chain

    mock_prompt.return_value = mock_prompt_instance

    # Mock llm
    mock_llm = Mock()
    mock_llm_factory.return_value = mock_llm

    # Mock question
    question = Mock(spec=Question)
    question.id = "test-id"
    question.content = "Explain photosynthesis"
    question.question_type = QuestionType.OPEN
    question.correct_answer = (
        "Process where plants convert light to energy"
    )
    question.explanation = "Photosynthesis explanation"

    # Execute
    result = await QuizService.evaluate_answer(
        question,
        "Plants use sunlight to make food"
    )

    # Assertions
    assert result["score"] == 0.85
    assert result["is_correct"] is True
    assert "Good answer" in result["feedback"]