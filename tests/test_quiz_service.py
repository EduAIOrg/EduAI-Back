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


@pytest.mark.asyncio
async def test_evaluate_mcq_question():
    """Test MCQ question evaluation with different answer prefixes and formats."""
    # Mock question
    question = Mock(spec=Question)
    question.id = "mcq-id"
    question.question_type = QuestionType.MCQ
    question.correct_answer = "Paris"
    question.options = ["Paris", "Rome", "Berlin", "London"]
    question.explanation = "Paris is correct."
    
    # 1. Exact match
    res1 = await QuizService.evaluate_answer(question, "Paris")
    assert res1["is_correct"] is True
    assert res1["score"] == 1.0
    
    # 2. Case mismatch
    res2 = await QuizService.evaluate_answer(question, "paris")
    assert res2["is_correct"] is True
    
    # 3. Letter match
    res3 = await QuizService.evaluate_answer(question, "a")
    assert res3["is_correct"] is True
    
    # 4. Letter with parenthesis
    res4 = await QuizService.evaluate_answer(question, "a)")
    assert res4["is_correct"] is True
    
    # 5. Letter with dot
    res5 = await QuizService.evaluate_answer(question, "A.")
    assert res5["is_correct"] is True

    # 6. Full prefixed option
    res6 = await QuizService.evaluate_answer(question, "A) Paris")
    assert res6["is_correct"] is True

    # 7. Wrong letter
    res7 = await QuizService.evaluate_answer(question, "b")
    assert res7["is_correct"] is False
    assert res7["score"] == 0.0

    # 8. Wrong text option
    res8 = await QuizService.evaluate_answer(question, "Rome")
    assert res8["is_correct"] is False
    assert res8["score"] == 0.0