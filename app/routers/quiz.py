"""Quiz router."""
import logging
import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.models.quiz import Quiz, Question, QuizResult, QuizStatus
from app.models.document import Document, DocumentStatus
from app.schemas.quiz import (
    QuizCreate,
    QuizResponse,
    QuizStatusResponse,
    QuizSubmit,
    QuizResultResponse,
    QuizListItem,
    AnswerFeedback,
    LacuneItem
)
from app.services.quiz_service import QuizService
from app.services.lacune_service import LacuneService
from app.tasks.quiz_tasks import generate_quiz_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/quiz", tags=["Quiz"])


@router.get("/", response_model=List[QuizListItem])
async def list_quizzes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[QuizListItem]:
    """
    List all quizzes for the current user.
    
    Args:
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        list: List of quizzes
    """
    try:
        result = await db.execute(
            select(Quiz)
            .where(Quiz.user_id == current_user.id)
            .order_by(Quiz.created_at.desc())
        )
        quizzes = result.scalars().all()
        
        # Build response with question count and last score
        response = []
        for quiz in quizzes:
            # Count questions
            q_count_result = await db.execute(
                select(func.count(Question.id))
                .where(Question.quiz_id == quiz.id)
            )
            question_count = q_count_result.scalar()
            
            # Get last score
            last_result = await db.execute(
                select(QuizResult)
                .where(QuizResult.quiz_id == quiz.id)
                .where(QuizResult.user_id == current_user.id)
                .order_by(QuizResult.created_at.desc())
                .limit(1)
            )
            last_quiz_result = last_result.scalar_one_or_none()
            
            response.append(QuizListItem(
                id=quiz.id,
                title=quiz.title,
                quiz_type=quiz.quiz_type,
                difficulty=quiz.difficulty,
                status=quiz.status,
                created_at=quiz.created_at,
                question_count=question_count,
                last_score=last_quiz_result.score if last_quiz_result else None
            ))
        
        return response
        
    except Exception as e:
        logger.error(f"Error listing quizzes: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list quizzes"
        )


@router.post("/generate", response_model=QuizResponse, status_code=status.HTTP_201_CREATED)
async def generate_quiz(
    request: QuizCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> QuizResponse:
    """
    Generate a new quiz from a document.
    
    Args:
        request: Quiz creation request
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        QuizResponse: Created quiz (status: generating)
    """
    try:
        # Validate document
        doc_result = await db.execute(
            select(Document).where(Document.id == request.document_id)
        )
        document = doc_result.scalar_one_or_none()
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        if document.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        if document.status != DocumentStatus.READY:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Document is not ready yet"
            )
        
        # Create quiz
        quiz = Quiz(
            user_id=current_user.id,
            document_id=request.document_id,
            title=request.title,
            quiz_type=request.quiz_type,
            difficulty=request.difficulty,
            status=QuizStatus.GENERATING
        )
        
        db.add(quiz)
        await db.commit()
        await db.refresh(quiz)
        
        # Launch async generation task
        generate_quiz_task.delay(str(quiz.id))
        
        logger.info(f"Quiz generation started: {quiz.id}")
        
        return QuizResponse.model_validate(quiz)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating quiz: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate quiz"
        )


@router.get("/{quiz_id}", response_model=QuizResponse)
async def get_quiz(
    quiz_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> QuizResponse:
    """
    Get a quiz with its questions.
    
    Args:
        quiz_id: Quiz UUID
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        QuizResponse: Quiz details with questions
    """
    try:
        result = await db.execute(
            select(Quiz).where(Quiz.id == quiz_id)
        )
        quiz = result.scalar_one_or_none()
        
        if not quiz:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Quiz not found"
            )
        
        if quiz.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        if quiz.status != QuizStatus.READY:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Quiz is not ready yet (status: {quiz.status})"
            )
        
        return QuizResponse.model_validate(quiz)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting quiz: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get quiz"
        )


@router.get("/{quiz_id}/status", response_model=QuizStatusResponse)
async def get_quiz_status(
    quiz_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> QuizStatusResponse:
    """
    Get quiz generation status.
    
    Args:
        quiz_id: Quiz UUID
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        QuizStatusResponse: Generation status
    """
    try:
        result = await db.execute(
            select(Quiz).where(Quiz.id == quiz_id)
        )
        quiz = result.scalar_one_or_none()
        
        if not quiz:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Quiz not found"
            )
        
        if quiz.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Generate progress message
        progress_messages = {
            QuizStatus.GENERATING: "Génération du quiz en cours...",
            QuizStatus.READY: "Quiz prêt",
            QuizStatus.ERROR: "Erreur lors de la génération"
        }
        
        return QuizStatusResponse(
            status=quiz.status,
            progress_message=progress_messages.get(
                quiz.status,
                "Statut inconnu"
            )
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting quiz status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get quiz status"
        )


@router.post("/{quiz_id}/submit", response_model=QuizResultResponse)
async def submit_quiz(
    quiz_id: uuid.UUID,
    submission: QuizSubmit,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> QuizResultResponse:
    """
    Submit quiz answers and get evaluation.
    
    Args:
        quiz_id: Quiz UUID
        submission: Quiz answers
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        QuizResultResponse: Evaluation results with feedback
    """
    try:
        # Get quiz
        result = await db.execute(
            select(Quiz).where(Quiz.id == quiz_id)
        )
        quiz = result.scalar_one_or_none()
        
        if not quiz:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Quiz not found"
            )
        
        if quiz.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        if quiz.status != QuizStatus.READY:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Quiz is not ready"
            )
        
        # Get questions
        q_result = await db.execute(
            select(Question)
            .where(Question.quiz_id == quiz_id)
            .order_by(Question.order_index)
        )
        questions = q_result.scalars().all()
        
        # Evaluate submission
        answers_dict = [
            {"question_id": str(ans.question_id), "answer": ans.answer}
            for ans in submission.answers
        ]
        
        evaluation = await QuizService.evaluate_quiz_submission(
            quiz=quiz,
            answers=answers_dict,
            db=db
        )
        
        # Analyze lacunes
        lacunes = await LacuneService.analyze_lacunes(
            quiz_result_data=evaluation,
            questions=questions,
            db=db
        )
        
        # Save result
        quiz_result = QuizResult(
            quiz_id=quiz_id,
            user_id=current_user.id,
            score=evaluation["overall_score"],
            answers={str(ans.question_id): ans.answer for ans in submission.answers},
            time_spent=submission.time_spent,
            lacunes=lacunes
        )
        
        db.add(quiz_result)
        await db.commit()
        await db.refresh(quiz_result)
        
        # Build response
        answer_feedback = [
            AnswerFeedback(
                question_id=uuid.UUID(eval_data["question_id"]),
                is_correct=eval_data["is_correct"],
                score=eval_data["score"],
                user_answer=eval_data["user_answer"],
                correct_answer=eval_data["correct_answer"],
                feedback=eval_data["feedback"]
            )
            for eval_data in evaluation["evaluations"]
        ]
        
        lacune_items = [
            LacuneItem(
                notion=lacune["notion"],
                level=lacune["level"],
                last_seen=lacune["last_seen"],
                recommendations=lacune.get("recommendations", [])
            )
            for lacune in lacunes
        ]
        
        logger.info(f"Quiz submitted: {quiz_id}, score: {evaluation['overall_score']:.2f}")
        
        return QuizResultResponse(
            id=quiz_result.id,
            quiz_id=quiz_result.quiz_id,
            user_id=quiz_result.user_id,
            score=quiz_result.score,
            time_spent=quiz_result.time_spent,
            created_at=quiz_result.created_at,
            answer_feedback=answer_feedback,
            lacunes=lacune_items
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting quiz: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit quiz"
        )


@router.get("/{quiz_id}/results", response_model=List[QuizResultResponse])
async def get_quiz_results(
    quiz_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[QuizResultResponse]:
    """
    Get all results for a quiz.
    
    Args:
        quiz_id: Quiz UUID
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        list: List of quiz results
    """
    try:
        # Verify quiz ownership
        quiz_result = await db.execute(
            select(Quiz).where(Quiz.id == quiz_id)
        )
        quiz = quiz_result.scalar_one_or_none()
        
        if not quiz:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Quiz not found"
            )
        
        if quiz.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Get results
        results = await db.execute(
            select(QuizResult)
            .where(QuizResult.quiz_id == quiz_id)
            .where(QuizResult.user_id == current_user.id)
            .order_by(QuizResult.created_at.desc())
        )
        quiz_results = results.scalars().all()
        
        # Get questions for feedback
        q_result = await db.execute(
            select(Question)
            .where(Question.quiz_id == quiz_id)
            .order_by(Question.order_index)
        )
        questions = q_result.scalars().all()
        question_map = {str(q.id): q for q in questions}
        
        # Build response
        response = []
        for qr in quiz_results:
            # Reconstruct answer feedback
            answer_feedback = []
            for q_id, user_answer in qr.answers.items():
                question = question_map.get(q_id)
                if question:
                    answer_feedback.append(AnswerFeedback(
                        question_id=uuid.UUID(q_id),
                        is_correct=True,  # Placeholder
                        score=qr.score,
                        user_answer=user_answer,
                        correct_answer=question.correct_answer,
                        feedback="Voir les détails de la soumission"
                    ))
            
            lacune_items = [
                LacuneItem(
                    notion=lacune["notion"],
                    level=lacune["level"],
                    last_seen=lacune["last_seen"],
                    recommendations=lacune.get("recommendations", [])
                )
                for lacune in qr.lacunes
            ]
            
            response.append(QuizResultResponse(
                id=qr.id,
                quiz_id=qr.quiz_id,
                user_id=qr.user_id,
                score=qr.score,
                time_spent=qr.time_spent,
                created_at=qr.created_at,
                answer_feedback=answer_feedback,
                lacunes=lacune_items
            ))
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting quiz results: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get quiz results"
        )
