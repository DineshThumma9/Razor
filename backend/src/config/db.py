import json
from ast import excepthandler
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from celery.app.base import logger
from config.config import settings
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from models.models import CustomerProfile, RecoveryState
from psycopg_pool import AsyncConnectionPool
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio.engine import create_async_engine
from sqlalchemy.ext.asyncio.session import AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, SQLModel, create_engine, select

_pool: AsyncConnectionPool | None = None
_checkpointer: AsyncPostgresSaver | None = None


engine = None
async_engine = None
SessionLocal = None
AsyncSessionLocal = None
_connection_failed = False


def _init_db():
    global engine, async_engine, SessionLocal, AsyncSessionLocal, _connection_failed

    if engine is not None:
        return

    if _connection_failed:
        raise RuntimeError("Database connection was alredy attempted and failed")

    if not settings.postgres_url:
        logger.critical("DATABASE_URL env var not set")
        _connection_failed = True
        raise RuntimeError("DATABASE URL not configured")

    try:
        logger.info("Connectiog to database")
        engine = create_engine(
            settings.postgres_url,
            pool_pre_ping=True,
            pool_recycle=settings.db_pool_recycle,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_timeout=settings.db_pool_timeout,
            connect_args={"connect_timeout": 5},
        )

        async_url = settings.postgres_url.replace(
            "postgresql://", "postgresql+psycopg://", 1
        )

        async_engine = create_async_engine(
            async_url,
            pool_pre_ping=True,
            pool_recycle=settings.db_pool_recycle,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_timeout=settings.db_pool_timeout,
            connect_args={"prepare_threshold": None},
        )
        SessionLocal = sessionmaker(autoflush=False, autocommit=False, bind=engine)
        AsyncSessionLocal = async_sessionmaker(
            bind=async_engine, autoflush=True, class_=AsyncSession, expire_on_commit=False
        )
        SQLModel.metadata.create_all(engine)
        logger.info("Database connection established")
    except Exception as e:
        logger.critical(f"Failed to connect to db:{str(e)}")
        _connection_failed = True
        raise SystemExit("Database connection failed")


async def get_db():
    _init_db()
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error(f"Database error:{e}")
            raise


@contextmanager
def get_task_db():
    _init_db()
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


async def init_checkpointer():
    global _pool, _checkpointer
    _pool = AsyncConnectionPool(
        conninfo=settings.database_url,
        max_size=settings.db_checkpointer_pool_size,
        max_lifetime=300,
        max_idle=30,
        kwargs={
            "autocommit": True,
            "prepare_threshold": None,
            "keepalives": 1,
            "keepalives_idle": 10,
            "keepalives_interval": 10,
            "keepalives_count": 5,
        },
        check=AsyncConnectionPool.check_connection,
        open=False,
    )
    await _pool.open()
    _checkpointer = AsyncPostgresSaver(_pool)
    await _checkpointer.setup()


def get_checkpointer() -> AsyncPostgresSaver:
    return _checkpointer


async def close_checkpointer():
    if _pool:
        await _pool.close()

async def close_db():
    global engine, async_engine
    if engine is not None:
        engine.dispose()
    if async_engine is not None:
        await async_engine.dispose()
