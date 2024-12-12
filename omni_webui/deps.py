from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import Session, create_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from .config import EnvironmentOnlySettings, get_env

EnvDepends = Annotated[EnvironmentOnlySettings, Depends(get_env)]


@lru_cache
def get_engine(env: EnvDepends) -> Engine | AsyncEngine:
    if "aiosqlite" in env.database_url or "asyncpg" in env.database_url:
        return create_async_engine(env.database_url)
    else:
        return create_engine(env.database_url)


EngineDepends = Annotated[Engine | AsyncEngine, Depends(get_engine)]


def get_session(engine: EngineDepends):
    if isinstance(engine, AsyncEngine):
        raise TypeError("Use get_async_session for async engine")
    with Session(engine) as session:
        yield session


SessionDepends = Annotated[Session, Depends(get_session)]


async def get_async_session(engine: EngineDepends):
    if isinstance(engine, Engine):
        raise TypeError("Use get_session for sync engine")
    async with AsyncSession(engine) as session:
        yield session


AsyncSessionDepends = Annotated[AsyncSession, Depends(get_async_session)]
