"""Celery tasks for quiz generation."""
import logging
from uuid import UUID
from celery import Task
from sqlalchemy import select

from app.celery_app import celery_app
from app.database import AsyncSessionLocal
from app.models.quiz import Quiz, QuizStatus
from app.services.quiz_service import QuizService

logger = logging.getLogger(__name__)


class QuizGenerationTask(Task):
    """Base task for quiz generation with error handling."""
    
    autoretry_for = (Exception,)
    retry_kwargs = {"max_retries": 2}
    retry_backoff = True
    retry_backoff_max = 300
    retry_jitter = True


@celery_app.task(bind=True, base=QuizGenerationTask, name="generate_quiz")
def generate_quiz_task(self, quiz_id: str) -> dict:
    """
    Generate quiz questions from a document.
    
    Args:
        quiz_id: Quiz UUID as string
        
    Returns:
        dict: Generation result
    """
    import asyncio
    
    logger.info(f"Starting quiz generation task for {quiz_id}")
    
    try:
        # Convert string to UUID
        quiz_uuid = UUID(quiz_id)
        
        # Run async generation
        result = asyncio.run(_generate_quiz_async(quiz_uuid))
        
        logger.info(f"Quiz generation completed for {quiz_id}")
        return result
        
    except Exception as e:
        logger.error(f"Error in quiz generation task: {e}")
        
        # Update quiz status to error
        asyncio.run(_update_quiz_status(quiz_id, QuizStatus.ERROR))
        
        raise


async def _generate_quiz_async(quiz_id: UUID) -> dict:
    """
    Async wrapper for quiz generation.
    
    Args:
        quiz_id: Quiz UUID
        
    Returns:
        dict: Generation result
    """
    async with AsyncSessionLocal() as db:
        try:
            # Get quiz
            result = await db.execute(
                select(Quiz).where(Quiz.id == quiz_id)
            )
            quiz = result.scalar_one_or_none()
            
            if not quiz:
                raise ValueError(f"Quiz {quiz_id} not found")
            
            # Generate questions
            await QuizService.generate_quiz_questions(
                quiz_id=quiz.id,
                document_id=quiz.document_id,
                quiz_type=quiz.quiz_type,
                difficulty=quiz.difficulty,
                num_questions=10,  # Default number
                db=db
            )
            
            # Update status to ready
            quiz.status = QuizStatus.READY
            await db.commit()
            
            return {
                "status": "success",
                "quiz_id": str(quiz_id),
                "message": "Quiz generated successfully"
            }
            
        except Exception as e:
            logger.error(f"Error generating quiz {quiz_id}: {e}")
            raise


async def _update_quiz_status(quiz_id: str, status: QuizStatus) -> None:
    """
    Update quiz status in database.
    
    Args:
        quiz_id: Quiz UUID as string
        status: New status
    """
    try:
        quiz_uuid = UUID(quiz_id)
        
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Quiz).where(Quiz.id == quiz_uuid)
            )
            quiz = result.scalar_one_or_none()
            
            if quiz:
                quiz.status = status
                await db.commit()
                logger.info(f"Updated quiz {quiz_id} status to {status}")
                
    except Exception as e:
        logger.error(f"Error updating quiz status: {e}")
