"""Notification service."""
import logging
import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for creating and managing notifications."""
    
    @staticmethod
    async def create_notification(
        db: AsyncSession,
        user_id: uuid.UUID,
        title: str,
        message: str,
        type: str = "system"
    ) -> Notification:
        """Create a new user notification."""
        try:
            notification = Notification(
                user_id=user_id,
                title=title,
                message=message,
                type=type,
                is_read=False
            )
            db.add(notification)
            await db.commit()
            await db.refresh(notification)
            logger.info(f"Notification created for user {user_id}: {title}")
            return notification
        except Exception as e:
            logger.error(f"Failed to create notification: {e}")
            await db.rollback()
            raise e
