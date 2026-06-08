"""Database configuration and session management."""
import logging
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy import event
from sqlalchemy.orm import declarative_base, Session, ORMExecuteState
from sqlalchemy.pool import NullPool

from app.config import settings

logger = logging.getLogger(__name__)


@event.listens_for(Session, "do_orm_execute")
def receive_do_orm_execute(orm_execute_state: ORMExecuteState):
    """Detect and log any lazy loading attempts in ORM queries."""
    if orm_execute_state.is_relationship_load and orm_execute_state.lazy_loaded_from:
        logger.warning(
            f"⚠️ TENTATIVE DE LAZY LOADING ORM DÉTECTÉE ! "
            f"Relation : {orm_execute_state.loader_strategy_path}. "
            f"Pour éviter l'erreur MissingGreenlet en mode asynchrone, utilisez selectinload() ou joinedload()."
        )

logger.warning(f"DATABASE_URL chargée = {settings.DATABASE_URL}")

# Create async engine
engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
    pool_pre_ping=True,
    poolclass=NullPool if "sqlite" in settings.DATABASE_URL else None,
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Base class for models
Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for getting async database sessions.
    
    Yields:
        AsyncSession: Database session
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables and run automatic schema updates."""
    from sqlalchemy import text
    async with engine.begin() as conn:
        # Enable pgvector extension
        try:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            logger.info("pgvector extension loaded/created successfully")
        except Exception as extension_err:
            logger.warning(f"Could not load/create pgvector extension: {extension_err}")

        # Add role column if not exists in users table
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(50) DEFAULT 'student';"))
            logger.info("users.role column checked/created successfully")
        except Exception as role_err:
            logger.warning(f"Could not add role column to users table: {role_err}")

        # Import all models to ensure they are registered
        from app.models import user, document, document_chunk, chat, quiz, study, notification, plan, subscription, payment, invoice  # noqa: F401
        
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully")

        # Seed default plans if table is empty
        result = await conn.execute(text("SELECT count(*) FROM plans;"))
        count = result.scalar()
        if count == 0:
            logger.info("Seeding default plans...")
            import json
            plans_data = [
                {
                    "id": "00000000-0000-0000-0000-000000000001",
                    "name": "Free",
                    "price": 0.0,
                    "currency": "FCFA",
                    "description": "Forfait de base gratuit pour découvrir la plateforme.",
                    "features": json.dumps([
                        "3 transcriptions / jour",
                        "5 résumés / jour",
                        "5 analyses / jour",
                        "10 chats / jour"
                    ]),
                    "daily_limits": json.dumps({
                        "transcription": 3,
                        "upload": 5,
                        "chat": 10
                    })
                },
                {
                    "id": "00000000-0000-0000-0000-000000000002",
                    "name": "Pro",
                    "price": 6500.0,
                    "currency": "FCFA",
                    "description": "Pour les étudiants et professionnels exigeants.",
                    "features": json.dumps([
                        "100 transcriptions / jour",
                        "100 résumés / jour",
                        "100 analyses / jour",
                        "100 chats / jour",
                        "Support standard"
                    ]),
                    "daily_limits": json.dumps({
                        "transcription": 100,
                        "upload": 100,
                        "chat": 100
                    })
                },
                {
                    "id": "00000000-0000-0000-0000-000000000003",
                    "name": "Enterprise",
                    "price": 65000.0,
                    "currency": "FCFA",
                    "description": "Pour les établissements scolaires et les entreprises.",
                    "features": json.dumps([
                        "Quotas personnalisés",
                        "Gestion multi-utilisateurs",
                        "Support prioritaire 24/7"
                    ]),
                    "daily_limits": json.dumps({
                        "transcription": 99999,
                        "upload": 99999,
                        "chat": 99999
                    })
                }
            ]
            for p_dict in plans_data:
                await conn.execute(
                    text(
                        "INSERT INTO plans (id, name, price, currency, description, features, daily_limits) "
                        "VALUES (:id, :name, :price, :currency, :description, :features, :daily_limits);"
                    ),
                    p_dict
                )
            logger.info("Seeding complete.")
        else:
            # Update existing plans to FCFA
            try:
                await conn.execute(text("UPDATE plans SET price = 0.0, currency = 'FCFA' WHERE id = '00000000-0000-0000-0000-000000000001';"))
                await conn.execute(text("UPDATE plans SET price = 6500.0, currency = 'FCFA' WHERE id = '00000000-0000-0000-0000-000000000002';"))
                await conn.execute(text("UPDATE plans SET price = 65000.0, currency = 'FCFA' WHERE id = '00000000-0000-0000-0000-000000000003';"))
                logger.info("Successfully updated default plans to FCFA")
            except Exception as update_err:
                logger.warning(f"Could not update plans currency to FCFA: {update_err}")


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()
    logger.info("Database connections closed")
