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
            "upload": 5,
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
        # Attempt to load limits dynamically from the active subscription plan
        limits = None
        try:
            from app.models.subscription import Subscription
            from app.models.plan import Plan
            
            sub_stmt = (
                select(Subscription)
                .where(Subscription.user_id == user.id)
                .where(Subscription.status == "active")
            )
            sub_res = await db.execute(sub_stmt)
            sub = sub_res.scalar_one_or_none()
            
            if sub:
                plan_stmt = select(Plan).where(Plan.id == sub.plan_id)
                plan_res = await db.execute(plan_stmt)
                plan = plan_res.scalar_one_or_none()
                if plan and plan.daily_limits:
                    limits = plan.daily_limits
        except Exception as e:
            logger.error(f"Failed to fetch active subscription plan limits dynamically: {e}")
            
        if not limits:
            user_plan = getattr(user, "plan", "free").lower()
            if user_plan not in QuotaService.LIMITS:
                user_plan = "free"
            limits = QuotaService.LIMITS[user_plan]
            
        limit = limits.get(action_type, 10)
        
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
        
        logger.info(f"User {user.id} usage for '{action_type}': {usage_count}/{limit}")
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
