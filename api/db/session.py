"""
api/db/session.py

Async SQLAlchemy engine and session factory.
"""

import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("APP_DATABASE_URL", "postgresql+asyncpg://ragfcup:changeme@localhost:5432/ragfcup")

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    """FastAPI dependency – yields an async DB session."""
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    """Create all tables (called on startup)."""
    from api.db.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
