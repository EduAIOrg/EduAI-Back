import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.database import Base


class Subscription(Base):
    """SaaS Subscription model mapping users to plans."""
    
    __tablename__ = "subscriptions"
    
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
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending"  # active, expired, cancelled, pending
    )
    start_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    end_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )
    
    # Relationships
    user: Mapped["User"] = relationship("User")
    plan: Mapped["Plan"] = relationship("Plan", back_populates="subscriptions")
    payments: Mapped[list["Payment"]] = relationship(
        "Payment",
        back_populates="subscription",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Subscription(id={self.id}, user_id={self.user_id}, status={self.status})>"
