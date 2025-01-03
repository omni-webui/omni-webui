import warnings
from pathlib import Path
from secrets import token_urlsafe
from typing import Annotated, Sequence

from fastapi import Depends
from mcp.client.stdio import StdioServerParameters
from pydantic import Field, field_serializer
from pydantic_settings import (
    BaseSettings,
    JsonConfigSettingsSource,
    PydanticBaseSettingsSource,
)

from omni_webui import D, get_package_dir


class Settings(
    BaseSettings,
    env_prefix="OMNI_WEBUI_",
    json_file=D.user_config_path / "omni-webui.json",
):
    title: str = "Omni WebUI"
    """Omni WebUI title."""

    secret_key: str = Field(default_factory=lambda: token_urlsafe(12))
    """Secret key for signing cookies and tokens."""

    frontend_dir: Path = get_package_dir("omni_webui") / "frontend"
    """Path to the frontend build directory."""

    data_dir: str = D.user_data_dir
    """Path to the data directory."""

    database_url: str = ""
    """Database URL."""

    mcpServers: dict[str, StdioServerParameters] = Field(default_factory=dict)

    def model_post_init(self, __context):
        if not self.database_url:
            path = D.user_data_path if "s3:" in self.data_dir else Path(self.data_dir)
            path.mkdir(parents=True, exist_ok=True)
            self.database_url = f"sqlite+aiosqlite:///{path / 'webui.db'}"
        if "s3:" in self.data_dir and self.database_url.startswith("sqlite"):
            warnings.warn(
                "Using SQLite database with S3 data directory is not recommended",
            )

    @field_serializer("frontend_dir")
    @classmethod
    def serialize_path(cls, path: Path) -> str:
        return str(path.resolve())

    def __hash__(self):
        return hash(self.model_dump_json())

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (init_settings, JsonConfigSettingsSource(settings_cls))

    def save(self):
        if (json_file := self.model_config.get("json_file")) is not None:
            if isinstance(json_file, Sequence):
                json_file = json_file[0]
            Path(json_file).write_text(
                self.model_dump_json(
                    indent=4,
                    exclude_defaults=True,
                    exclude_unset=True,
                )
            )

    @property
    def upload_dir(self) -> str:
        if "s3:" in self.data_dir:
            return self.data_dir + "/uploads"
        return str(Path(self.data_dir) / "uploads")


SettingsDepends = Annotated[Settings, Depends(lambda: Settings())]
