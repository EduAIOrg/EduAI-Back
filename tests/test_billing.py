"""Tests for billing and subscriptions router."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime, timedelta

from fastapi import HTTPException
from app.routers.billing import (
    get_plans,
    get_current_subscription,
    create_subscription,
    upgrade_subscription,
    cancel_subscription,
    get_payment_history,
    get_invoices,
    payment_webhook
)
from app.models.user import User
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.payment import Payment
from app.models.invoice import Invoice
from app.schemas.billing import (
    SubscriptionCreateRequest,
    SubscriptionUpgradeRequest
)


@pytest.mark.asyncio
async def test_get_plans():
    mock_db = AsyncMock()
    mock_plan = MagicMock(spec=Plan)
    mock_plan.id = uuid4()
    mock_plan.name = "Pro"
    mock_plan.price = 9.99
    mock_plan.currency = "EUR"
    mock_plan.description = "Pro Plan"
    mock_plan.features = ["feature 1"]
    mock_plan.daily_limits = {"chat": 100}

    mock_result_db = MagicMock()
    mock_result_db.scalars.return_value.all.return_value = [mock_plan]
    mock_db.execute.return_value = mock_result_db

    response = await get_plans(db=mock_db)
    assert len(response) == 1
    assert response[0].name == "Pro"
    assert response[0].price == 9.99


@pytest.mark.asyncio
async def test_get_current_subscription():
    mock_db = AsyncMock()
    mock_user = MagicMock(spec=User)
    mock_user.id = uuid4()

    mock_sub = MagicMock(spec=Subscription)
    mock_sub.id = uuid4()
    mock_sub.user_id = mock_user.id
    mock_sub.status = "active"
    mock_sub.start_date = datetime.utcnow()
    mock_sub.end_date = datetime.utcnow() + timedelta(days=30)
    mock_sub.plan = MagicMock(spec=Plan)
    mock_sub.plan.name = "Pro"

    mock_result_db = MagicMock()
    mock_result_db.scalars.return_value.first.return_value = mock_sub
    mock_db.execute.return_value = mock_result_db

    response = await get_current_subscription(current_user=mock_user, db=mock_db)
    assert response.status == "active"
    assert response.id == mock_sub.id


@pytest.mark.asyncio
async def test_create_subscription():
    mock_db = AsyncMock()
    mock_user = MagicMock(spec=User)
    mock_user.id = uuid4()

    mock_plan = MagicMock(spec=Plan)
    mock_plan.id = uuid4()
    mock_plan.name = "Pro"
    mock_plan.price = 9.99
    mock_plan.currency = "EUR"

    mock_sub = MagicMock(spec=Subscription)
    mock_sub.id = uuid4()
    mock_sub.user_id = mock_user.id
    mock_sub.plan_id = mock_plan.id
    mock_sub.status = "pending"

    # Mock DB queries inside create_subscription
    with patch("app.services.billing_service.BillingService.create_subscription", return_value=mock_sub):
        payload = SubscriptionCreateRequest(plan_id=mock_plan.id, provider="stripe")
        response = await create_subscription(payload=payload, current_user=mock_user, db=mock_db)
        assert response.status == "pending"
        assert response.user_id == mock_user.id


@pytest.mark.asyncio
async def test_upgrade_subscription():
    mock_db = AsyncMock()
    mock_user = MagicMock(spec=User)
    mock_user.id = uuid4()

    mock_plan = MagicMock(spec=Plan)
    mock_plan.id = uuid4()
    mock_plan.name = "Enterprise"

    mock_sub = MagicMock(spec=Subscription)
    mock_sub.id = uuid4()
    mock_sub.user_id = mock_user.id
    mock_sub.plan_id = mock_plan.id
    mock_sub.status = "pending"

    with patch("app.services.billing_service.BillingService.upgrade_subscription", return_value=mock_sub):
        payload = SubscriptionUpgradeRequest(plan_id=mock_plan.id, provider="stripe")
        response = await upgrade_subscription(payload=payload, current_user=mock_user, db=mock_db)
        assert response.status == "pending"


@pytest.mark.asyncio
async def test_cancel_subscription():
    mock_db = AsyncMock()
    mock_user = MagicMock(spec=User)
    mock_user.id = uuid4()

    mock_sub = MagicMock(spec=Subscription)
    mock_sub.id = uuid4()
    mock_sub.status = "cancelled"

    with patch("app.services.billing_service.BillingService.cancel_subscription", return_value=mock_sub):
        response = await cancel_subscription(current_user=mock_user, db=mock_db)
        assert response.status == "cancelled"


@pytest.mark.asyncio
async def test_get_payment_history():
    mock_db = AsyncMock()
    mock_user = MagicMock(spec=User)
    mock_user.id = uuid4()

    mock_payment = MagicMock(spec=Payment)
    mock_payment.id = uuid4()
    mock_payment.amount = 9.99
    mock_payment.status = "completed"

    mock_result_db = MagicMock()
    mock_result_db.scalars.return_value.all.return_value = [mock_payment]
    mock_db.execute.return_value = mock_result_db

    response = await get_payment_history(current_user=mock_user, db=mock_db)
    assert len(response) == 1
    assert response[0].amount == 9.99
    assert response[0].status == "completed"


@pytest.mark.asyncio
async def test_get_invoices():
    mock_db = AsyncMock()
    mock_user = MagicMock(spec=User)
    mock_user.id = uuid4()

    mock_invoice = MagicMock(spec=Invoice)
    mock_invoice.id = uuid4()
    mock_invoice.invoice_number = "INV-12345"

    mock_result_db = MagicMock()
    mock_result_db.scalars.return_value.all.return_value = [mock_invoice]
    mock_db.execute.return_value = mock_result_db

    response = await get_invoices(current_user=mock_user, db=mock_db)
    assert len(response) == 1
    assert response[0].invoice_number == "INV-12345"


@pytest.mark.asyncio
async def test_payment_webhook():
    mock_db = AsyncMock()
    payload = {"transaction_id": "tx_123456", "status": "completed"}

    with patch("app.services.billing_service.BillingService.handle_webhook", return_value={"status": "success"}):
        response = await payment_webhook(provider="stripe", payload=payload, db=mock_db)
        assert response["status"] == "success"
