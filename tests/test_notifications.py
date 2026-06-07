"""Tests for notifications router."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime

from fastapi import HTTPException
from app.routers.notifications import (
    get_notifications,
    get_unread_notifications,
    mark_notification_as_read,
    mark_all_notifications_as_read,
    delete_notification
)
from app.models.user import User
from app.models.notification import Notification


@pytest.mark.asyncio
async def test_get_notifications():
    mock_db = AsyncMock()
    mock_user = MagicMock(spec=User)
    mock_user.id = uuid4()
    
    mock_notification = MagicMock(spec=Notification)
    mock_notification.id = uuid4()
    mock_notification.user_id = mock_user.id
    mock_notification.title = "Test Notification"
    mock_notification.message = "This is a test notification."
    mock_notification.type = "system"
    mock_notification.is_read = False
    mock_notification.created_at = datetime.utcnow()
    
    mock_result_db = MagicMock()
    mock_result_db.scalars.return_value.all.return_value = [mock_notification]
    mock_db.execute.return_value = mock_result_db
    
    response = await get_notifications(db=mock_db, current_user=mock_user)
    
    assert len(response) == 1
    assert response[0].title == "Test Notification"
    assert response[0].is_read is False


@pytest.mark.asyncio
async def test_get_unread_notifications():
    mock_db = AsyncMock()
    mock_user = MagicMock(spec=User)
    mock_user.id = uuid4()
    
    mock_notification = MagicMock(spec=Notification)
    mock_notification.id = uuid4()
    mock_notification.user_id = mock_user.id
    mock_notification.title = "Unread Notification"
    mock_notification.message = "Another test notification."
    mock_notification.type = "document"
    mock_notification.is_read = False
    mock_notification.created_at = datetime.utcnow()
    
    mock_result_db = MagicMock()
    mock_result_db.scalars.return_value.all.return_value = [mock_notification]
    mock_db.execute.return_value = mock_result_db
    
    response = await get_unread_notifications(db=mock_db, current_user=mock_user)
    
    assert len(response) == 1
    assert response[0].title == "Unread Notification"
    assert response[0].is_read is False


@pytest.mark.asyncio
async def test_mark_notification_as_read():
    mock_db = AsyncMock()
    mock_user = MagicMock(spec=User)
    mock_user.id = uuid4()
    
    mock_notification = MagicMock(spec=Notification)
    mock_notification.id = uuid4()
    mock_notification.user_id = mock_user.id
    mock_notification.title = "Test Notification"
    mock_notification.message = "Another test notification."
    mock_notification.type = "system"
    mock_notification.is_read = False
    mock_notification.created_at = datetime.utcnow()
    
    mock_result_db = MagicMock()
    mock_result_db.scalar_one_or_none.return_value = mock_notification
    mock_db.execute.return_value = mock_result_db
    
    response = await mark_notification_as_read(
        notification_id=mock_notification.id,
        db=mock_db,
        current_user=mock_user
    )
    
    assert response.is_read is True
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_mark_all_notifications_as_read():
    mock_db = AsyncMock()
    mock_user = MagicMock(spec=User)
    mock_user.id = uuid4()
    
    response = await mark_all_notifications_as_read(db=mock_db, current_user=mock_user)
    
    assert response["status"] == "success"
    mock_db.execute.assert_called_once()
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_delete_notification():
    mock_db = AsyncMock()
    mock_user = MagicMock(spec=User)
    mock_user.id = uuid4()
    
    mock_notification = MagicMock(spec=Notification)
    mock_notification.id = uuid4()
    mock_notification.user_id = mock_user.id
    mock_notification.title = "Test Notification"
    
    mock_result_db = MagicMock()
    mock_result_db.scalar_one_or_none.return_value = mock_notification
    mock_db.execute.return_value = mock_result_db
    
    response = await delete_notification(
        notification_id=mock_notification.id,
        db=mock_db,
        current_user=mock_user
    )
    
    assert response["status"] == "success"
    mock_db.delete.assert_called_once_with(mock_notification)
    mock_db.commit.assert_called_once()
