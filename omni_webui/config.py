import importlib.util
from functools import lru_cache
from pathlib import Path
from secrets import token_urlsafe
from typing import Self, cast

from pydantic import Field, field_serializer, field_validator, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SecretsSettingsSource,
    SettingsConfigDict,
)

from ._compat import find_case_path
from ._logger import logger


@lru_cache
def get_package_dir(name: str) -> Path:
    spec = importlib.util.find_spec(name)
    if spec is None:
        raise ImportError(f"{name} module not found")
    if spec.submodule_search_locations is None:
        raise ValueError(f"{name} module not installed correctly")
    return Path(spec.submodule_search_locations[0])


class EnvironmentOnlySettings(BaseSettings):
    """Settings from environment variables (and dotenv files)"""

    data_dir: Path = get_package_dir("open_webui") / "data"
    frontend_build_dir: Path = get_package_dir("omni_webui") / "frontend"
    database_url: str = ""

    LD_LIBRARY_PATH: list[Path] = Field(default_factory=list)

    @model_validator(mode="after")
    def setup_default_values(self) -> Self:
        if not self.data_dir.exists():
            self.data_dir.mkdir(parents=True)
        if not self.database_url:
            self.database_url = f"sqlite+aiosqlite:///{self.data_dir / 'webui.db'}"
        return self

    @field_validator("LD_LIBRARY_PATH")
    def append_cuda_libs(cls, v):
        if isinstance(v, str):
            return [Path(p) for p in v.split(":")]
        return v

    @field_serializer("LD_LIBRARY_PATH")
    def serialize_cuda_libs(self, v):
        return ":".join(str(p) for p in v)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return env_settings, dotenv_settings

    def __hash__(self):
        return hash(self.model_dump_json())


class Settings(BaseSettings):
    secret_key: str = Field(default_factory=lambda: token_urlsafe(12))

    model_config = SettingsConfigDict(env_prefix="webui_", secrets_dir=Path.cwd())

    @model_validator(mode="after")
    def save_secret_key(self):
        secrets_dir = self.model_config.get("secrets_dir")
        if (
            secrets_dir
            and not (
                key_file := Path(
                    secrets_dir
                    if isinstance(secrets_dir, (str, Path))
                    else secrets_dir[0]
                )
                / ".webui_secret_key"
            ).exists()
        ):
            logger.info(f"Generating a new secret key and saving it to {key_file}")
            key_file.write_text(self.secret_key)
        return self

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        cast(SecretsSettingsSource, file_secret_settings).find_case_path = staticmethod(
            find_case_path
        )
        return init_settings, env_settings, dotenv_settings, file_secret_settings


@lru_cache
def get_env() -> EnvironmentOnlySettings:
    return EnvironmentOnlySettings()


@lru_cache
def get_settings() -> Settings:
    return Settings()
