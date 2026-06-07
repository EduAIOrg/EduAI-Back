"""Notification schemas."""
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class NotificationBase(BaseModel):
    """Base notification schema."""
    title: str = Field(..., description="Notification title")
    message: str = Field(..., description="Notification description/message")
    type: str = Field(default="system", description="Notification type (document, ia, compte, system)")


class NotificationResponse(NotificationBase):
    """Notification response schema."""
    id: UUID = Field(..., description="Notification ID")
    user_id: UUID = Field(..., description="User ID")
    is_read: bool = Field(..., description="Read status")
    created_at: datetime = Field(..., description="Notification creation timestamp")
    
    model_config = {
        "from_attributes": True
    }


class NotificationUnreadCount(BaseModel):
    """Unread count schema."""
    unread_count: int = Field(..., description="Number of unread notifications")
