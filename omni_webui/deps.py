from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from .config import EnvironmentOnlySettings, get_env

EnvDepends = Annotated[EnvironmentOnlySettings, Depends(get_env)]


@lru_cache
def get_engine(env: EnvDepends) -> AsyncEngine:
    return create_async_engine(env.database_url)


EngineDepends = Annotated[AsyncEngine, Depends(get_engine)]


async def get_session(engine: EngineDepends):
    async with AsyncSession(engine) as session:
        yield session


SessionDepends = Annotated[AsyncSession, Depends(get_session)]
