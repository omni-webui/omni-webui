from datetime import datetime
from typing import Annotated

from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.sql.functions import func
from sqlmodel import Field, Session, SQLModel, col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ..config import Config as ConfigData
from ..deps import get_engine, get_env


class Config(SQLModel, table=True):
    id: Annotated[int | None, Field(primary_key=True)] = None
    data: ConfigData = Field(
        default_factory=ConfigData, sa_type=ConfigData.as_sa_type()
    )
    version: int = 0
    created_at: Annotated[
        datetime, Field(sa_column_kwargs={"server_default": func.now()})
    ]
    updated_at: Annotated[
        datetime | None, Field(nullable=True, sa_column_kwargs={"onupdate": func.now()})
    ] = None


async def get_config() -> ConfigData:
    engine = get_engine(get_env())
    statement = select(Config).order_by(col(Config.id).desc())
    match engine:
        case AsyncEngine() as async_engine:
            async with AsyncSession(async_engine) as session:
                config = (await session.exec(statement)).first()
        case Engine():
            with Session(engine) as session:
                config = session.exec(statement).first()
    return ConfigData() if config is None else config.data
