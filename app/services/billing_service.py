import logging
import uuid
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.payment import Payment
from app.models.invoice import Invoice
from app.models.user import User
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


class BillingService:
    """Service handling SaaS subscription, payments, webhooks, and invoice operations."""

    @staticmethod
    async def get_plans(db: AsyncSession) -> List[Plan]:
        """Fetch all plans."""
        result = await db.execute(select(Plan).order_by(Plan.price))
        return list(result.scalars().all())

    @staticmethod
    async def get_current_subscription(db: AsyncSession, user_id: uuid.UUID) -> Optional[Subscription]:
        """Fetch user's current active subscription (or latest)."""
        result = await db.execute(
            select(Subscription)
            .options(selectinload(Subscription.plan))
            .where(Subscription.user_id == user_id)
            .where(Subscription.status.in_(["active", "cancelled", "pending"]))
            .order_by(Subscription.end_date.desc())
        )
        return result.scalars().first()

    @staticmethod
    async def create_subscription(
        db: AsyncSession,
        user_id: uuid.UUID,
        plan_id: uuid.UUID,
        provider: str
    ) -> Subscription:
        """Create a new subscription and initiate a pending payment."""
        # 1. Fetch Plan
        plan_res = await db.execute(select(Plan).where(Plan.id == plan_id))
        plan = plan_res.scalar_one_or_none()
        if not plan:
            raise ValueError("Plan not found")

        # 2. Cancel previous active subscriptions
        active_sub = await BillingService.get_current_subscription(db, user_id)
        if active_sub:
            active_sub.status = "expired"

        # 3. Create Subscription (pending/active depending on price)
        status = "active" if plan.price == 0.0 else "pending"
        start_date = datetime.utcnow()
        end_date = start_date + timedelta(days=30)

        subscription = Subscription(
            user_id=user_id,
            plan_id=plan_id,
            status=status,
            start_date=start_date,
            end_date=end_date
        )
        db.add(subscription)
        await db.commit()
        await db.refresh(subscription)

        # 4. Create Payment log
        payment_status = "completed" if plan.price == 0.0 else "pending"
        payment = Payment(
            user_id=user_id,
            subscription_id=subscription.id,
            amount=plan.price,
            currency=plan.currency,
            provider=provider,
            provider_transaction_id=f"tx_{uuid.uuid4().hex[:12]}",
            status=payment_status
        )
        db.add(payment)
        await db.commit()
        await db.refresh(payment)

        # 5. Handle user role/plan mapping
        if plan.price == 0.0:
            user_res = await db.execute(select(User).where(User.id == user_id))
            user = user_res.scalar_one_or_none()
            if user:
                user.plan = plan.name.lower()
                await db.commit()

            # Create notification
            await NotificationService.create_notification(
                db=db,
                user_id=user_id,
                title="Abonnement activé",
                message=f"Votre forfait '{plan.name}' a été activé avec succès.",
                type="compte"
            )

        return subscription

    @staticmethod
    async def upgrade_subscription(
        db: AsyncSession,
        user_id: uuid.UUID,
        plan_id: uuid.UUID,
        provider: str
    ) -> Subscription:
        """Upgrade active subscription to a new tier."""
        return await BillingService.create_subscription(db, user_id, plan_id, provider)

    @staticmethod
    async def cancel_subscription(db: AsyncSession, user_id: uuid.UUID) -> Subscription:
        """Cancel subscription (active until period ends)."""
        sub = await BillingService.get_current_subscription(db, user_id)
        if not sub:
            raise ValueError("No active subscription found")

        sub.status = "cancelled"
        await db.commit()
        await db.refresh(sub)

        # Create notification
        await NotificationService.create_notification(
            db=db,
            user_id=user_id,
            title="Abonnement annulé",
            message="Votre abonnement a été annulé mais reste actif jusqu'à la fin de la période de facturation.",
            type="compte"
        )
        return sub

    @staticmethod
    async def get_payment_history(db: AsyncSession, user_id: uuid.UUID) -> List[Payment]:
        """Retrieve user's payment history."""
        result = await db.execute(
            select(Payment)
            .where(Payment.user_id == user_id)
            .order_by(Payment.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_invoices(db: AsyncSession, user_id: uuid.UUID) -> List[Invoice]:
        """Retrieve user's invoices."""
        result = await db.execute(
            select(Invoice)
            .where(Invoice.user_id == user_id)
            .order_by(Invoice.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def handle_webhook(db: AsyncSession, provider: str, payload: dict) -> dict:
        """Process payments provider webhooks (Stripe, PayPal, Mobile Money)."""
        logger.info(f"Processing webhook for provider={provider} payload={payload}")
        
        transaction_id = payload.get("transaction_id")
        status = payload.get("status")  # completed, failed, refunded
        
        if not transaction_id or not status:
            raise ValueError("Invalid webhook payload")

        # Find payment by transaction id
        result = await db.execute(select(Payment).where(Payment.provider_transaction_id == transaction_id))
        payment = result.scalar_one_or_none()
        if not payment:
            # Fallback check subscription
            sub_id = payload.get("subscription_id")
            if sub_id:
                sub_uuid = uuid.UUID(sub_id)
                res = await db.execute(select(Payment).where(Payment.subscription_id == sub_uuid))
                payment = res.scalar_one_or_none()

        if not payment:
            raise ValueError(f"Transaction {transaction_id} not found in database")

        # Update payment status
        payment.status = status
        
        # Load subscription & plan
        sub_res = await db.execute(
            select(Subscription)
            .options(selectinload(Subscription.plan))
            .where(Subscription.id == payment.subscription_id)
        )
        sub = sub_res.scalar_one_or_none()

        if sub:
            if status == "completed":
                sub.status = "active"
                # Update user table plan field
                user_res = await db.execute(select(User).where(User.id == payment.user_id))
                user = user_res.scalar_one_or_none()
                if user:
                    user.plan = sub.plan.name.lower()
                
                # Generate Invoice
                invoice_number = f"INV-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
                invoice = Invoice(
                    user_id=payment.user_id,
                    payment_id=payment.id,
                    invoice_number=invoice_number,
                    pdf_url=f"/invoices/{invoice_number}.pdf"
                )
                db.add(invoice)
                
                # Notifications
                await NotificationService.create_notification(
                    db=db,
                    user_id=payment.user_id,
                    title="Paiement validé",
                    message=f"Le paiement de {payment.amount} {payment.currency} a été validé.",
                    type="compte"
                )
                await NotificationService.create_notification(
                    db=db,
                    user_id=payment.user_id,
                    title="Abonnement activé",
                    message=f"Votre forfait '{sub.plan.name}' a été activé avec succès.",
                    type="compte"
                )
                await NotificationService.create_notification(
                    db=db,
                    user_id=payment.user_id,
                    title="Facture disponible",
                    message=f"La facture {invoice_number} est désormais téléchargeable.",
                    type="document"
                )
            elif status == "failed":
                sub.status = "expired"
                await NotificationService.create_notification(
                    db=db,
                    user_id=payment.user_id,
                    title="Paiement échoué",
                    message=f"Le paiement de votre abonnement a échoué. Veuillez vérifier vos coordonnées bancaires.",
                    type="compte"
                )
            elif status == "refunded":
                sub.status = "expired"
                await NotificationService.create_notification(
                    db=db,
                    user_id=payment.user_id,
                    title="Remboursement effectué",
                    message=f"Un remboursement a été effectué sur votre mode de paiement original.",
                    type="compte"
                )

        await db.commit()
        return {"status": "success", "message": f"Processed webhook for {provider}"}
