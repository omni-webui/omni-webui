"""Configuration module."""

import importlib.util
import warnings
from functools import lru_cache
from pathlib import Path
from secrets import token_urlsafe
from typing import (
    Literal,
    Self,
    Sequence,
    cast,
)

from mcp import StdioServerParameters
from platformdirs import PlatformDirs
from pydantic import (
    Field,
    field_serializer,
    model_validator,
)
from pydantic_settings import (
    BaseSettings,
    JsonConfigSettingsSource,
    PydanticBaseSettingsSource,
    SecretsSettingsSource,
)
from typing_extensions import deprecated

from ._compat import find_case_path, save_secret_key
from ._logger import logger


@lru_cache
def get_package_dir(name: str) -> Path:
    """Get the directory of the package."""
    spec = importlib.util.find_spec(name)
    if spec is None:
        raise ImportError(f"{name} module not found")
    if spec.submodule_search_locations is None:
        raise ValueError(f"{name} module not installed correctly")
    return Path(spec.submodule_search_locations[0])


APP_NAME = "omni-webui"
D = PlatformDirs(appname=APP_NAME)


@deprecated("Backward compatibility with Open WebUI, will be removed >= 1.0")
class Environments(BaseSettings, secrets_dir=Path.cwd()):
    """Settings from environment variables (and dotenv files), backward compatible with Open WebUI."""

    data_dir: Path = D.user_data_path
    frontend_build_dir: Path = get_package_dir("omni_webui") / "frontend"
    database_url: str = ""
    enable_admin_export: bool = True
    enable_admin_chat_access: bool = True
    webui_name: str = "Omni WebUI"
    webui_secret_key: str = Field(default_factory=lambda: token_urlsafe(12))
    webui_auth: bool = True
    webui_auth_trusted_email_header: str | None = None
    webui_auth_trusted_name_header: str | None = None
    webui_session_cookie_same_site: Literal["lax", "strict", "none"] = "lax"
    webui_session_cookie_secure: bool = False

    @model_validator(mode="after")
    def setup_default_values(self) -> Self:
        """Set up default values."""
        if not self.data_dir.exists():
            self.data_dir.mkdir(parents=True)
        if not self.database_url:
            self.database_url = f"sqlite:///{self.data_dir / 'webui.db'}"
        return self

    @model_validator(mode="after")
    def save_secret_key(self):
        """Save the secret key to the secrets directory."""
        secrets_dir = cast(Path, self.model_config.get("secrets_dir"))
        if not (key_file := secrets_dir / ".webui_secret_key").exists():
            logger.info(f"Generating a new secret key and saving it to {key_file}")
            key_file.write_text(self.webui_secret_key)
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
        """Customize the settings sources."""
        cast(SecretsSettingsSource, file_secret_settings).find_case_path = staticmethod(
            find_case_path
        )
        return init_settings, env_settings, dotenv_settings, file_secret_settings

    def __hash__(self):
        return hash(self.model_dump_json())


class Settings(
    BaseSettings,
    env_prefix="OMNI_WEBUI_",
    json_file=D.user_config_path / "omni-webui.json",
):
    """Omni WebUI settings."""

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
        """Post-initialization hook."""
        if not self.database_url:
            path = D.user_data_path if "s3:" in self.data_dir else Path(self.data_dir)
            path.mkdir(parents=True, exist_ok=True)
            self.database_url = f"sqlite+aiosqlite:///{path / 'webui.db'}"
        if "s3:" in self.data_dir and self.database_url.startswith("sqlite"):
            warnings.warn(
                "Using SQLite database with S3 data directory is not recommended",
            )
        save_secret_key(self.secret_key, Path.cwd() / ".env")

    @field_serializer("frontend_dir")
    @classmethod
    def serialize_path(cls, path: Path) -> str:
        """Serialize a path to a string."""
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
        """Customize the settings sources."""
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            file_secret_settings,
            JsonConfigSettingsSource(settings_cls),
        )

    def save(self):
        """Save the settings to the JSON file."""
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
        """Path to the upload directory."""
        if "s3:" in self.data_dir:
            return self.data_dir + "/uploads"
        return str(Path(self.data_dir) / "uploads")
