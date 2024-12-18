from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from .config import Environments, Settings

# https://github.com/pydantic/pydantic-settings/issues/183
EnvDepends = Annotated[Environments, Depends(lambda: Environments())]
SettingsDepends = Annotated[Settings, Depends(lambda: Settings())]


@lru_cache
def get_engine(settings: SettingsDepends) -> AsyncEngine:
    return create_async_engine(settings.database_url)


async def get_session(engine: Annotated[AsyncEngine, Depends(get_engine)]):
    async with AsyncSession(engine) as session:
        yield session


SessionDepends = Annotated[AsyncSession, Depends(get_session)]
