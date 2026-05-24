"""Learning gap (lacune) analysis service."""
import json
import logging
from typing import List, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.quiz import QuizResult, Question
from app.ai.llm_factory import LLMFactory
from app.ai.prompts import get_lacune_analysis_prompt

logger = logging.getLogger(__name__)


class LacuneService:
    """Service for analyzing learning gaps."""
    
    @staticmethod
    async def analyze_lacunes(
        quiz_result_data: Dict[str, Any],
        questions: List[Question],
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """
        Analyze learning gaps from quiz results.
        
        Args:
            quiz_result_data: Quiz evaluation results
            questions: List of Question objects
            db: Database session
            
        Returns:
            list: List of identified learning gaps
        """
        try:
            # Filter failed questions (score < 0.6)
            failed_evaluations = [
                e for e in quiz_result_data["evaluations"]
                if e["score"] < 0.6
            ]
            
            if not failed_evaluations:
                logger.info("No failed questions, no lacunes to analyze")
                return []
            
            # Create question map
            question_map = {str(q.id): q for q in questions}
            
            # Prepare failed questions text
            failed_questions_text = []
            for eval_data in failed_evaluations:
                question_id = eval_data["question_id"]
                question = question_map.get(question_id)
                
                if question:
                    failed_questions_text.append(
                        f"Question: {question.content}\n"
                        f"Réponse correcte: {question.correct_answer}\n"
                        f"Réponse de l'étudiant: {eval_data['user_answer']}\n"
                        f"Score: {eval_data['score']:.2f}\n"
                    )
            
            if not failed_questions_text:
                return []
            
            failed_text = "\n---\n".join(failed_questions_text)
            
            # Use LLM to analyze lacunes
            llm = LLMFactory.create_evaluation_llm()
            prompt = get_lacune_analysis_prompt()
            
            chain = prompt | llm
            response = await chain.ainvoke({
                "failed_questions": failed_text
            })
            
            # Parse JSON response
            response_text = response.content.strip()
            
            # Extract JSON from response
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            lacunes_data = json.loads(response_text)
            
            if "lacunes" not in lacunes_data:
                logger.warning("No lacunes key in response")
                return []
            
            # Add timestamp to each lacune
            lacunes = []
            for lacune in lacunes_data["lacunes"]:
                lacunes.append({
                    "notion": lacune["notion"],
                    "level": lacune["level"],
                    "last_seen": datetime.utcnow().isoformat(),
                    "recommendations": lacune.get("recommendations", [])
                })
            
            logger.info(f"Identified {len(lacunes)} learning gaps")
            return lacunes
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing lacunes JSON: {e}")
            logger.error(f"Response text: {response_text}")
            return []
        except Exception as e:
            logger.error(f"Error analyzing lacunes: {e}")
            return []
    
    @staticmethod
    async def get_aggregated_lacunes(
        user_id: str,
        db: AsyncSession,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get aggregated learning gaps for a user.
        
        Args:
            user_id: User UUID
            db: Database session
            limit: Maximum number of lacunes to return
            
        Returns:
            list: Aggregated learning gaps
        """
        try:
            # Get recent quiz results
            result = await db.execute(
                select(QuizResult)
                .where(QuizResult.user_id == user_id)
                .order_by(QuizResult.created_at.desc())
                .limit(20)
            )
            quiz_results = result.scalars().all()
            
            if not quiz_results:
                return []
            
            # Aggregate lacunes
            lacune_map: Dict[str, Dict[str, Any]] = {}
            
            for quiz_result in quiz_results:
                for lacune in quiz_result.lacunes:
                    notion = lacune["notion"]
                    
                    if notion not in lacune_map:
                        lacune_map[notion] = {
                            "notion": notion,
                            "level": lacune["level"],
                            "last_seen": lacune["last_seen"],
                            "occurrences": 1,
                            "recommendations": lacune.get("recommendations", [])
                        }
                    else:
                        # Update existing lacune
                        lacune_map[notion]["occurrences"] += 1
                        
                        # Keep most recent last_seen
                        if lacune["last_seen"] > lacune_map[notion]["last_seen"]:
                            lacune_map[notion]["last_seen"] = lacune["last_seen"]
                            lacune_map[notion]["level"] = lacune["level"]
                        
                        # Merge recommendations
                        existing_recs = set(lacune_map[notion]["recommendations"])
                        new_recs = lacune.get("recommendations", [])
                        lacune_map[notion]["recommendations"] = list(
                            existing_recs.union(set(new_recs))
                        )[:5]  # Keep top 5
            
            # Sort by occurrences and severity
            severity_order = {"weak": 3, "medium": 2, "strong": 1}
            
            sorted_lacunes = sorted(
                lacune_map.values(),
                key=lambda x: (
                    severity_order.get(x["level"], 0),
                    x["occurrences"]
                ),
                reverse=True
            )
            
            return sorted_lacunes[:limit]
            
        except Exception as e:
            logger.error(f"Error getting aggregated lacunes: {e}")
            return []
