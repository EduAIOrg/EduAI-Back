"""Quiz generation and evaluation service."""
import json
import logging
from typing import List, Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.quiz import Quiz, Question, QuizType, QuizDifficulty, QuestionType
from app.models.document import Document
from app.ai.vector_store import vector_store_manager
from app.ai.llm_factory import LLMFactory
from app.ai.prompts import get_quiz_generation_prompt, get_answer_evaluation_prompt

logger = logging.getLogger(__name__)


class QuizService:
    """Service for quiz generation and evaluation."""
    
    @staticmethod
    async def generate_quiz_questions(
        quiz_id: UUID,
        document_id: UUID,
        quiz_type: QuizType,
        difficulty: QuizDifficulty,
        num_questions: int,
        db: AsyncSession
    ) -> None:
        """
        Generate quiz questions from a document.
        
        Args:
            quiz_id: Quiz UUID
            document_id: Document UUID
            quiz_type: Type of quiz (mcq/open/mixed)
            difficulty: Difficulty level
            num_questions: Number of questions to generate
            db: Database session
        """
        try:
            logger.info(f"Generating {num_questions} questions for quiz {quiz_id}")
            
            # Get random chunks from document
            chunks = vector_store_manager.get_random_chunks(
                document_id=document_id,
                n=min(num_questions * 2, 20)  # Get more chunks for variety
            )
            
            if not chunks:
                raise ValueError("No content available from document")
            
            # Combine chunks
            document_content = "\n\n".join(chunks)
            
            # Truncate if too long
            max_chars = 12000
            if len(document_content) > max_chars:
                document_content = document_content[:max_chars]
            
            # Create LLM and prompt
            llm = LLMFactory.create_quiz_llm()
            prompt = get_quiz_generation_prompt()
            
            # Generate questions
            chain = prompt | llm
            response = await chain.ainvoke({
                "document_content": document_content,
                "num_questions": num_questions,
                "quiz_type": quiz_type.value,
                "difficulty": difficulty.value
            })
            
            # Parse JSON response
            response_text = response.content.strip()
            
            # Extract JSON from response (handle markdown code blocks)
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            questions_data = json.loads(response_text)
            
            if "questions" not in questions_data:
                raise ValueError("Invalid response format: missing 'questions' key")
            
            # Create Question objects
            for idx, q_data in enumerate(questions_data["questions"][:num_questions]):
                question = Question(
                    quiz_id=quiz_id,
                    content=q_data["content"],
                    question_type=QuestionType(q_data["type"]),
                    options=q_data.get("options"),
                    correct_answer=q_data["correct_answer"],
                    explanation=q_data["explanation"],
                    order_index=idx
                )
                db.add(question)
            
            await db.commit()
            logger.info(f"Successfully generated {num_questions} questions")
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing quiz JSON: {e}")
            logger.error(f"Response text: {response_text}")
            raise ValueError(f"Failed to parse quiz questions: {e}")
        except Exception as e:
            logger.error(f"Error generating quiz questions: {e}")
            raise
    
    @staticmethod
    async def evaluate_answer(
        question: Question,
        student_answer: str
    ) -> Dict[str, Any]:
        """
        Evaluate a student's answer.
        
        Args:
            question: Question object
            student_answer: Student's answer
            
        Returns:
            dict: Evaluation result with score and feedback
        """
        try:
            if question.question_type == QuestionType.MCQ:
                # Direct comparison for MCQ
                is_correct = student_answer.strip().upper() == question.correct_answer.strip().upper()
                score = 1.0 if is_correct else 0.0
                
                feedback = (
                    f"Correct! {question.explanation}" if is_correct
                    else f"Incorrect. La bonne réponse est: {question.correct_answer}. {question.explanation}"
                )
                
                return {
                    "score": score,
                    "feedback": feedback,
                    "is_correct": is_correct
                }
            else:
                # Use LLM for open questions
                llm = LLMFactory.create_evaluation_llm()
                prompt = get_answer_evaluation_prompt()
                
                chain = prompt | llm
                response = await chain.ainvoke({
                    "question": question.content,
                    "correct_answer": question.correct_answer,
                    "student_answer": student_answer
                })
                
                # Parse JSON response
                response_text = response.content.strip()
                
                # Extract JSON from response
                if "```json" in response_text:
                    response_text = response_text.split("```json")[1].split("```")[0].strip()
                elif "```" in response_text:
                    response_text = response_text.split("```")[1].split("```")[0].strip()
                
                eval_data = json.loads(response_text)
                
                score = float(eval_data["score"])
                feedback = eval_data["feedback"]
                is_correct = score >= 0.6
                
                return {
                    "score": score,
                    "feedback": feedback,
                    "is_correct": is_correct
                }
                
        except Exception as e:
            logger.error(f"Error evaluating answer: {e}")
            # Return default evaluation on error
            return {
                "score": 0.0,
                "feedback": "Erreur lors de l'évaluation de la réponse.",
                "is_correct": False
            }
    
    @staticmethod
    async def evaluate_quiz_submission(
        quiz: Quiz,
        answers: List[Dict[str, Any]],
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Evaluate all answers in a quiz submission.
        
        Args:
            quiz: Quiz object
            answers: List of answer submissions
            db: Database session
            
        Returns:
            dict: Evaluation results
        """
        try:
            # Get all questions
            result = await db.execute(
                select(Question)
                .where(Question.quiz_id == quiz.id)
                .order_by(Question.order_index)
            )
            questions = result.scalars().all()
            
            # Create answer map
            answer_map = {str(ans["question_id"]): ans["answer"] for ans in answers}
            
            # Evaluate each answer
            evaluations = []
            total_score = 0.0
            
            for question in questions:
                student_answer = answer_map.get(str(question.id), "")
                
                if not student_answer:
                    # No answer provided
                    evaluation = {
                        "question_id": str(question.id),
                        "score": 0.0,
                        "feedback": "Aucune réponse fournie.",
                        "is_correct": False,
                        "user_answer": "",
                        "correct_answer": question.correct_answer
                    }
                else:
                    # Evaluate answer
                    eval_result = await QuizService.evaluate_answer(question, student_answer)
                    evaluation = {
                        "question_id": str(question.id),
                        "score": eval_result["score"],
                        "feedback": eval_result["feedback"],
                        "is_correct": eval_result["is_correct"],
                        "user_answer": student_answer,
                        "correct_answer": question.correct_answer
                    }
                
                evaluations.append(evaluation)
                total_score += evaluation["score"]
            
            # Calculate overall score
            overall_score = total_score / len(questions) if questions else 0.0
            
            return {
                "overall_score": overall_score,
                "evaluations": evaluations,
                "total_questions": len(questions),
                "correct_answers": sum(1 for e in evaluations if e["is_correct"])
            }
            
        except Exception as e:
            logger.error(f"Error evaluating quiz submission: {e}")
            raise
