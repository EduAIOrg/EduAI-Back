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
        from app.models import user, document, document_chunk, chat, quiz, study  # noqa: F401
        
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully")


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()
    logger.info("Database connections closed")
