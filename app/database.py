from datetime import datetime, timezone
from functools import lru_cache
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings
from app.core.exceptions import DatabaseConfigurationError


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@lru_cache
def _create_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(database_url, pool_pre_ping=True)


def get_engine() -> AsyncEngine:
    database_url = get_settings().database_url
    if database_url is None:
        raise DatabaseConfigurationError()
    return _create_engine(database_url.get_secret_value())


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def init_database() -> None:
    from app import db_models

    engine = get_engine()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def dispose_database() -> None:
    if get_settings().database_url is not None:
        await get_engine().dispose()


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with get_session_factory()() as session:
        yield session
