import uuid
from datetime import datetime
from sqlalchemy import String, Float, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.database import Base


class Payment(Base):
    """SaaS Payment transaction log model."""
    
    __tablename__ = "payments"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    amount: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )
    currency: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="EUR"
    )
    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False  # stripe, paypal, orange_money, mtn_momo
    )
    provider_transaction_id: Mapped[str] = mapped_column(
        String(255),
        nullable=True,
        index=True
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending"  # pending, completed, failed, refunded
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    
    # Relationships
    user: Mapped["User"] = relationship("User")
    subscription: Mapped["Subscription"] = relationship("Subscription", back_populates="payments")
    invoices: Mapped[list["Invoice"]] = relationship(
        "Invoice",
        back_populates="payment",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Payment(id={self.id}, amount={self.amount}, status={self.status})>"
