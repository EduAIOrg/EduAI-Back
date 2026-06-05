"""SaaS Quotas Enforcement Service."""
import logging
from uuid import UUID
from datetime import datetime, time
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.quota import UsageLog

logger = logging.getLogger(__name__)


class QuotaService:
    """Service to handle SaaS usage logs and quota enforcement for Free/Premium users."""
    
    LIMITS = {
        "free": {
            "chat": 10,
            "upload": 3,
            "quiz": 3,
            "transcription": 3
        },
        "premium": {
            "chat": 999999,
            "upload": 999999,
            "quiz": 999999,
            "transcription": 999999
        }
    }
    
    @staticmethod
    async def check_quota(db: AsyncSession, user: User, action_type: str) -> bool:
        """
        Check if user is within their plan's limits for the day.
        
        Args:
            db: Database session
            user: User object containing plan and role
            action_type: Action string ("chat", "upload", "quiz", "transcription")
            
        Returns:
            bool: True if allowed, False if quota exceeded
        """
        user_plan = getattr(user, "plan", "free").lower()
        if user_plan not in QuotaService.LIMITS:
            user_plan = "free"
            
        limit = QuotaService.LIMITS[user_plan].get(action_type, 10)
        
        # Get start of today
        today_start = datetime.combine(datetime.utcnow().date(), time.min)
        
        # Count usages today
        stmt = (
            select(func.count(UsageLog.id))
            .where(UsageLog.user_id == user.id)
            .where(UsageLog.action_type == action_type)
            .where(UsageLog.created_at >= today_start)
        )
        res = await db.execute(stmt)
        usage_count = res.scalar() or 0
        
        logger.info(f"User {user.id} usage for '{action_type}': {usage_count}/{limit} (plan: {user_plan})")
        return usage_count < limit

    @staticmethod
    async def increment_usage(db: AsyncSession, user_id: UUID, action_type: str) -> None:
        """
        Record a new action usage log in the database.
        
        Args:
            db: Database session
            user_id: User UUID
            action_type: Action string ("chat", "upload", "quiz", "transcription")
        """
        try:
            log = UsageLog(user_id=user_id, action_type=action_type)
            db.add(log)
            await db.commit()
        except Exception as e:
            logger.error(f"Failed to increment usage log: {e}")
            await db.rollback()
