import asyncio
from datetime import datetime
from typing import Annotated

from pydantic_settings import (
    BaseSettings,
    InitSettingsSource,
    PydanticBaseSettingsSource,
)
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.sql.functions import func
from sqlmodel import Field, Session, SQLModel, col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ..deps import get_engine, get_env
from ._types import MutableBaseModel


class SQLModelSettingSource(InitSettingsSource):
    table_cls: type[SQLModel]

    def __init__(
        self,
        settings_cls: type[BaseSettings],
        table_class: type["Config"],
    ) -> None:
        self.table_cls = table_class
        engine = get_engine(get_env())
        statement = select(table_class).order_by(col(table_class.id).desc())
        match engine:
            case AsyncEngine() as async_engine:

                async def fetch_data():
                    async with AsyncSession(async_engine) as session:
                        return (await session.exec(statement)).first()

                data = asyncio.run(fetch_data())
            case Engine():
                with Session(engine) as session:
                    data = session.exec(statement).first()
        if data is None:
            data = ConfigData()
        super().__init__(settings_cls, data.model_dump())


class APIKey(MutableBaseModel, BaseSettings, extra="allow"):
    enable: Annotated[bool, Field(alias="ENABLE_API_KEY")] = True


class Auth(MutableBaseModel, BaseSettings, extra="allow"):
    api_key: APIKey = Field(default_factory=APIKey)


class ConfigData(MutableBaseModel, extra="allow"):
    auth: Auth = Field(default_factory=Auth)


class ConfigSettings(ConfigData):
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            file_secret_settings,
            SQLModelSettingSource(settings_cls, table_class=Config),
        )


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
