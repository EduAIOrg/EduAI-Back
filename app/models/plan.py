import uuid
from sqlalchemy import String, Float, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Plan(Base):
    """SaaS Plan model detailing limits and features."""
    
    __tablename__ = "plans"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    name: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True
    )
    price: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0
    )
    currency: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="EUR"
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=True
    )
    features: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list
    )
    daily_limits: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict
    )
    
    # Relationships
    subscriptions: Mapped[list["Subscription"]] = relationship(
        "Subscription",
        back_populates="plan",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Plan(id={self.id}, name={self.name}, price={self.price})>"
