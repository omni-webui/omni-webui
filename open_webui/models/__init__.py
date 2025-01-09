"""Models for the Open Web UI."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from open_webui.env import EnvDep


@lru_cache
def get_engine(env: EnvDep) -> AsyncEngine:
    """Get the database engine."""
    if "sqlite" in env.DATABASE_URL and not env.DATABASE_URL.startswith("sqlite+"):
        env.DATABASE_URL = env.DATABASE_URL.replace("sqlite", "sqlite+aiosqlite")
    if "postgresql" in env.DATABASE_URL and not env.DATABASE_URL.startswith(
        "postgresql+"
    ):
        env.DATABASE_URL = env.DATABASE_URL.replace("postgresql", "postgresql+asyncpg")
    return create_async_engine(env.DATABASE_URL)


EngineDep = Annotated[AsyncEngine, Depends(get_engine)]


async def get_session(engine: EngineDep):
    """Get the database session."""
    async with AsyncSession(engine) as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]
