from datetime import datetime
from typing import Annotated

from fastapi import Depends
from sqlalchemy.sql.functions import func
from sqlmodel import Field, SQLModel, col, select

from ..config import Config as ConfigData
from ..deps import SessionDepends


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


async def get_config(session: SessionDepends) -> ConfigData:
    statement = select(Config).order_by(col(Config.id).desc())
    config = (await session.exec(statement)).first()
    return ConfigData() if config is None else config.data


ConfigDepends = Annotated[ConfigData, Depends(get_config)]
