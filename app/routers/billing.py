import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.billing import (
    PlanResponse,
    SubscriptionResponse,
    PaymentResponse,
    InvoiceResponse,
    SubscriptionCreateRequest,
    SubscriptionUpgradeRequest,
)
from app.services.billing_service import BillingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["Billing & Subscriptions"])


@router.get("/plans", response_model=List[PlanResponse])
async def get_plans(db: AsyncSession = Depends(get_db)):
    """Retrieve all available subscription plans."""
    try:
        return await BillingService.get_plans(db)
    except Exception as e:
        logger.error(f"Error fetching plans: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve plans"
        )


@router.get("/subscriptions/current", response_model=SubscriptionResponse)
async def get_current_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve user's active subscription status."""
    sub = await BillingService.get_current_subscription(db, current_user.id)
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active subscription found"
        )
    return sub


@router.post("/subscriptions/create", response_model=SubscriptionResponse)
async def create_subscription(
    payload: SubscriptionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Initiate a new plan subscription."""
    try:
        return await BillingService.create_subscription(
            db=db,
            user_id=current_user.id,
            plan_id=payload.plan_id,
            provider=payload.provider
        )
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err)
        )
    except Exception as e:
        logger.error(f"Error creating subscription: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create subscription"
        )


@router.post("/subscriptions/upgrade", response_model=SubscriptionResponse)
async def upgrade_subscription(
    payload: SubscriptionUpgradeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Upgrade user subscription to a higher plan."""
    try:
        return await BillingService.upgrade_subscription(
            db=db,
            user_id=current_user.id,
            plan_id=payload.plan_id,
            provider=payload.provider
        )
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err)
        )
    except Exception as e:
        logger.error(f"Error upgrading subscription: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upgrade subscription"
        )


@router.post("/subscriptions/cancel", response_model=SubscriptionResponse)
async def cancel_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Cancel subscription at period end."""
    try:
        return await BillingService.cancel_subscription(db, current_user.id)
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err)
        )
    except Exception as e:
        logger.error(f"Error cancelling subscription: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel subscription"
        )


@router.get("/payments/history", response_model=List[PaymentResponse])
async def get_payment_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve payment transaction history."""
    try:
        return await BillingService.get_payment_history(db, current_user.id)
    except Exception as e:
        logger.error(f"Error fetching payments: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve payments"
        )


@router.get("/invoices", response_model=List[InvoiceResponse])
async def get_invoices(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve PDF invoices list."""
    try:
        return await BillingService.get_invoices(db, current_user.id)
    except Exception as e:
        logger.error(f"Error fetching invoices: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve invoices"
        )


@router.post("/webhooks/{provider}")
async def payment_webhook(
    provider: str,
    payload: dict,
    db: AsyncSession = Depends(get_db)
):
    """Unified webhook endpoint for Stripe, PayPal, Orange Money, MTN MoMo callbacks."""
    try:
        return await BillingService.handle_webhook(db, provider, payload)
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err)
        )
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook execution failed"
        )
