"""Notifications router."""
import logging
import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.models.notification import Notification
from app.schemas.notification import NotificationResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=List[NotificationResponse])
async def get_notifications(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> List[NotificationResponse]:
    """Get all notifications for the current user."""
    try:
        result = await db.execute(
            select(Notification)
            .where(Notification.user_id == current_user.id)
            .order_by(Notification.created_at.desc())
        )
        notifications = result.scalars().all()
        return notifications
    except Exception as e:
        logger.error(f"Error fetching notifications: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch notifications"
        )


@router.get("/unread", response_model=List[NotificationResponse])
async def get_unread_notifications(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> List[NotificationResponse]:
    """Get all unread notifications for the current user."""
    try:
        result = await db.execute(
            select(Notification)
            .where(Notification.user_id == current_user.id, Notification.is_read == False)
            .order_by(Notification.created_at.desc())
        )
        notifications = result.scalars().all()
        return notifications
    except Exception as e:
        logger.error(f"Error fetching unread notifications: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch unread notifications"
        )


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_as_read(
    notification_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> NotificationResponse:
    """Mark a notification as read."""
    try:
        result = await db.execute(
            select(Notification)
            .where(Notification.id == notification_id, Notification.user_id == current_user.id)
        )
        notification = result.scalar_one_or_none()
        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found"
            )
            
        notification.is_read = True
        await db.commit()
        await db.refresh(notification)
        return notification
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating notification: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update notification"
        )


@router.patch("/read-all", status_code=status.HTTP_200_OK)
async def mark_all_notifications_as_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mark all notifications as read for the current user."""
    try:
        await db.execute(
            update(Notification)
            .where(Notification.user_id == current_user.id, Notification.is_read == False)
            .values(is_read=True)
        )
        await db.commit()
        return {"status": "success", "message": "All notifications marked as read"}
    except Exception as e:
        logger.error(f"Error marking all notifications as read: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark notifications as read"
        )


@router.delete("/{notification_id}", status_code=status.HTTP_200_OK)
async def delete_notification(
    notification_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a notification."""
    try:
        result = await db.execute(
            select(Notification)
            .where(Notification.id == notification_id, Notification.user_id == current_user.id)
        )
        notification = result.scalar_one_or_none()
        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found"
            )
            
        await db.delete(notification)
        await db.commit()
        return {"status": "success", "message": "Notification deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting notification: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete notification"
        )
