"""Configuration module for Open Web UI."""

import json
import logging
import os
import re
import shutil
from datetime import UTC, datetime, timedelta
from functools import cached_property
from itertools import zip_longest
from pathlib import Path
from typing import (
    Annotated,
    Any,
    Generic,
    Iterable,
    Literal,
    NotRequired,
    Optional,
    TypedDict,
    TypeVar,
    get_args,
    get_type_hints,
)
from urllib.parse import urlparse

import chromadb.config
from fastapi import Depends
from loguru import logger
from ollama import AsyncClient
from openai import AsyncOpenAI
from openai.types.audio import SpeechCreateParams, SpeechModel
from pydantic import (
    AliasChoices,
    Field,
    TypeAdapter,
    ValidationError,
    ValidatorFunctionWrapHandler,
    WrapValidator,
    field_validator,
)
from pydantic_settings import (
    BaseSettings as _BaseSettings,
)
from pydantic_settings import (
    NoDecode,
)
from sqlmodel import Field as SQLModelField
from sqlmodel import SQLModel, col, func, select
from typing_extensions import deprecated

from open_webui.env import (
    DATABASE_URL,
    OFFLINE_MODE,
    OPEN_WEBUI_DIR,
    OPENAI_BASE_URL,
    env,
)
from open_webui.env import WEBUI_FAVICON_URL as WEBUI_FAVICON_URL
from open_webui.internal.db import get_db
from open_webui.models import SessionDep

from ._types import MutableBaseModel as BaseModel


class BaseSettings(BaseModel, _BaseSettings):
    """Mutable BaseSettings class."""


class AudioConfig(BaseModel):
    """Audio configuration."""

    class TTS(BaseSettings, env_prefix="AUDIO_TTS_"):
        """Text-to-speech configuration."""

        class Azure(BaseSettings, env_prefix="AUDIO_TTS_AZURE_"):
            """Azure configuration."""

            speech_region: str = "eastus"  # East US
            speech_output_format: str = "audio-24khz-160kbitrate-mono-mp3"

        azure: Azure = Field(default_factory=Azure)
        engine: str = ""
        model: str = get_args(SpeechModel)[0]
        voice: str = get_args(get_type_hints(SpeechCreateParams)["voice"])[0]
        split_on: str = "punctuation"

    tts: TTS = Field(default_factory=TTS)

    class STT(BaseSettings, env_prefix="AUDIO_STT_"):
        """Speech-to-text configuration."""

        engine: str = ""

    stt: STT = Field(default_factory=STT)


@deprecated("Open WebUI self-defined rules, would be remove @1.0")
def parse_duration(duration: str) -> timedelta | None:
    """Parse the duration."""
    if duration == "-1" or duration == "0":
        return None

    # Regular expression to find number and unit pairs
    pattern = r"(-?\d+(\.\d+)?)(ms|s|m|h|d|w)"
    matches = re.findall(pattern, duration)

    if not matches:
        raise ValueError("Invalid duration string")

    total_duration = timedelta()

    for number, _, unit in matches:
        number = float(number)
        if unit == "ms":
            total_duration += timedelta(milliseconds=number)
        elif unit == "s":
            total_duration += timedelta(seconds=number)
        elif unit == "m":
            total_duration += timedelta(minutes=number)
        elif unit == "h":
            total_duration += timedelta(hours=number)
        elif unit == "d":
            total_duration += timedelta(days=number)
        elif unit == "w":
            total_duration += timedelta(weeks=number)

    return total_duration


@deprecated("Backward-compatible with Open WebUI, would be removed @1.0")
def unparse_duration(duration: timedelta | None) -> str:
    """Unparse the duration."""
    if duration is None:
        return "-1"
    return f"{duration.total_seconds()}s"


@deprecated("Backward-compatible with Open WebUI, would be removed @1.0")
def validate_duration(value: Any, handler: ValidatorFunctionWrapHandler):
    """Validate the duration."""
    try:
        return handler(value)
    except ValidationError:
        try:
            return parse_duration(value)
        except ValueError:
            raise ValidationError


class AuthConfig(BaseSettings):
    """Authentication configuration."""

    class APIKey(BaseSettings):
        """API key configuration."""

        enable: Annotated[
            bool, Field(validation_alias=AliasChoices("ENABLE_API_KEY", "enable"))
        ] = True
        endpoint_restrictions: Annotated[
            bool,
            Field(
                validation_alias=AliasChoices(
                    "ENABLE_API_KEY_ENDPOINT_RESTRICTIONS", "endpoint_restrictions"
                )
            ),
        ] = False
        allowed_endpoints: Annotated[list[str], NoDecode] = Field(default_factory=list)

        @field_validator("allowed_endpoints", mode="before")
        @classmethod
        def parse_comma_separated_values(cls, v: Any) -> list[str]:
            """Parse the semicolon-separated values."""
            if isinstance(v, str):
                return v.split(",")
            if isinstance(v, list) and all(isinstance(i, str) for i in v):
                return v
            raise ValidationError("Invalid value")

    api_key: APIKey = Field(default_factory=APIKey)
    jwt_expiry: Annotated[
        timedelta | None,
        Field(validation_alias=AliasChoices("JWT_EXPIRES_IN", "jwt_expiry")),
        WrapValidator(validate_duration),
    ] = None


class ArenaModel(BaseModel):
    """Arena model configuration."""

    class Meta(BaseModel):
        """Arena model meta configuration."""

        profile_image_url: str = "/favicon.png"
        description: str = "Submit your questions to anonymous AI chatbots and vote on the best response."

    id: str = "arena-model"
    name: str = "Arena Model"
    meta: Meta = Field(default_factory=Meta)


class Evaluation(BaseModel):
    """Evaluation configuration."""

    class Arena(BaseSettings):
        """Evaluation Arena configuration."""

        enable: Annotated[
            bool,
            Field(
                validation_alias=AliasChoices(
                    "ENABLE_EVALUATION_ARENA_MODELS", "enable"
                )
            ),
        ] = True
        models: list[ArenaModel] = Field(default_factory=lambda: [ArenaModel()])

    arena: Arena = Field(default_factory=Arena)


class ImageGenerationConfig(BaseSettings):
    """Image generation configuration."""

    enable: Annotated[
        bool, Field(validation_alias=AliasChoices("ENABLE_IMAGE_GENERATION", "enable"))
    ] = True


class LDAPConfig(BaseModel):
    """LDAP configuration."""

    enable: Annotated[
        bool, Field(validation_alias=AliasChoices("ENABLE_LDAP", "enable"))
    ] = False


class OAuthProvider(TypedDict):
    """OAuth provider model."""

    client_id: str
    client_secret: str
    scope: str
    redirect_uri: str
    name: NotRequired[str]
    server_metadata_url: str


type UserRole = Literal["pending", "user", "admin"]


class OAuthConfig(BaseModel, env_prefix="OAUTH_"):
    """OAuth configuration."""

    class Provider(BaseSettings):
        """OAuth provider configuration."""

        client_id: str = ""
        client_secret: str = ""
        scope: str = "openid email profile"
        redirect_uri: str = ""

    class Google(Provider, env_prefix="GOOGLE_"):
        """Google OAuth provider configuration."""

    class Microsoft(Provider, env_prefix="MICROSOFT_"):
        """Microsoft OAuth provider configuration."""

        tenant_id: str = ""

    class OIDC(Provider, env_prefix="OAUTH_"):
        """OIDC OAuth provider configuration."""

        provider_url: Annotated[
            str, Field(serialization_alias="server_metadata_url")
        ] = ""
        provider_name: str = "SSO"
        username_claim: str = "name"
        avatar_claim: Annotated[
            str,
            Field(validation_alias=AliasChoices("OAUTH_PICTURE_CLAIM", "avatar_claim")),
        ] = "picture"
        email_claim: str = "email"

        roles_claim: str = "roles"
        group_claim: str = "groups"
        allowed_roles: list[str] = ["user", "admin"]
        admin_roles: list[str] = ["admin"]

    enable_signup: Annotated[
        bool,
        Field(validation_alias=AliasChoices("ENABLE_OAUTH_SIGNUP", "enable_signup")),
    ] = False
    enable_role_mapping: Annotated[
        bool,
        Field(
            validation_alias=AliasChoices(
                "ENABLE_OAUTH_ROLE_MANAGEMENT", "enable_role_mapping"
            )
        ),
    ] = False
    enable_group_mapping: Annotated[
        bool,
        Field(
            validation_alias=AliasChoices(
                "ENABLE_OAUTH_GROUP_MANAGEMENT", "enable_group_mapping"
            )
        ),
    ] = False
    merge_accounts_by_email: Annotated[
        bool,
        Field(
            validation_alias=AliasChoices(
                "OAUTH_MERGE_ACCOUNTS_BY_EMAIL", "merge_accounts_by_email"
            )
        ),
    ] = False
    google: Google = Field(default_factory=Google)
    microsoft: Microsoft = Field(default_factory=Microsoft)
    oidc: OIDC = Field(default_factory=OIDC)
    roles_claim: str = "roles"
    allowed_roles: Annotated[set[UserRole], NoDecode] = Field(default={"user", "admin"})
    admin_roles: Annotated[set[str], NoDecode] = Field(default={"admin"})
    allowed_domains: Annotated[set[str], NoDecode] = Field(default={"*"})

    @field_validator("allowed_roles", "admin_roles", mode="before")
    @classmethod
    def parse_comma_separated_values(cls, v: Any) -> set[UserRole]:
        """Parse the comma-separated values."""
        if isinstance(v, str):
            return TypeAdapter(set[UserRole]).validate_python(set(v.split(",")))
        if isinstance(v, Iterable) and all(isinstance(i, str) for i in v):
            return set(v)
        raise ValidationError("Invalid value")

    @field_validator("allowed_domains", mode="before")
    @classmethod
    def parse_comma_separated_domains(cls, v: Any) -> set[str]:
        """Parse the comma-separated domains."""
        if isinstance(v, str):
            return set(v.split(","))
        if isinstance(v, Iterable) and all(isinstance(i, str) for i in v):
            return set(v)
        raise ValidationError("Invalid value")

    @property
    def providers(self) -> dict[str, OAuthProvider]:
        """Get the OAuth providers."""
        providers = {}
        if self.google.client_id and self.google.client_secret:
            providers["google"] = self.google.model_dump() | {
                "server_metadata_url": "https://accounts.google.com/.well-known/openid-configuration"
            }
        if (
            self.microsoft.client_id
            and self.microsoft.client_secret
            and self.microsoft.tenant_id
        ):
            providers["microsoft"] = self.microsoft.model_dump(
                exclude={"tenant_id"}
            ) | {
                "server_metadata_url": f"https://login.microsoftonline.com/{self.microsoft.tenant_id}/v2.0/.well-known/openid-configuration",
            }
        if self.oidc.client_id and self.oidc.client_secret and self.oidc.provider_url:
            providers["oidc"] = self.oidc.model_dump(
                by_alias=True,
                include={
                    "client_id",
                    "client_secret",
                    "server_metadata_url",
                    "scope",
                    "name",
                    "redirect_uri",
                },
            )
        return providers


class ClientConfig(BaseModel):
    """OpenAI/Ollama client configuration."""

    enable: bool = True
    prefix_id: str | None = None


class OllamaConfig(BaseSettings, env_prefix="OLLAMA_"):
    """Ollama configuration."""

    enable: Annotated[
        bool, Field(validation_alias=AliasChoices("ENABLE_OLLAMA_API", "enable"))
    ] = True
    base_urls: Annotated[list[str], NoDecode] = Field(default_factory=list)
    api_configs: dict[str, ClientConfig] = Field(default_factory=dict)

    @field_validator("base_urls", mode="before")
    @classmethod
    def parse_semicolon_separated_values(cls, v: Any) -> list[str]:
        """Parse the semicolon-separated values."""
        if isinstance(v, str):
            return v.split(";")
        if isinstance(v, list) and all(isinstance(i, str) for i in v):
            return v
        raise ValidationError("Invalid value")

    def model_post_init(self, __context):
        """Post-initialization model hook."""
        self.base_urls = [base_url for base_url in self.base_urls if base_url]
        if not self.base_urls:
            self.base_urls = ["http://127.0.0.1:11434"]

    @cached_property
    def clients(self) -> list[AsyncOpenAI]:
        """Get the Ollama clients."""
        return [
            AsyncOpenAI(
                api_key="ollama",
                base_url=base_url,
            )
            for base_url in self.base_urls
            if (api_config := self.api_configs.get(base_url)) is None
            or api_config.enable
        ]

    @cached_property
    def ollama_clients(self) -> list[AsyncClient]:
        """Get the Ollama clients."""
        return [AsyncClient(host=base_url) for base_url in self.base_urls]


class OpenAIConfig(BaseSettings, env_prefix="OPENAI_"):
    """OpenAI configuration."""

    enable: Annotated[
        bool, Field(validation_alias=AliasChoices("ENABLE_OPENAI_API", "enable"))
    ] = True
    api_keys: Annotated[list[str], NoDecode] = Field(default_factory=list)
    api_base_urls: Annotated[list[str], NoDecode] = Field(default_factory=list)
    api_configs: dict[str, ClientConfig] = Field(default_factory=dict)

    @field_validator("api_keys", "api_base_urls", mode="before")
    @classmethod
    def parse_semicolon_separated_values(cls, v: Any) -> list[str]:
        """Parse the semicolon-separated values."""
        if isinstance(v, str):
            return v.split(";")
        if isinstance(v, list) and all(isinstance(i, str) for i in v):
            return v
        raise ValidationError("Invalid value")

    @cached_property
    def clients(self) -> list[AsyncOpenAI]:
        """Get the OpenAI clients."""
        return [
            AsyncOpenAI(
                api_key=api_key,
                base_url=base_url,
            )
            for api_key, base_url in zip_longest(
                self.api_keys,
                self.api_base_urls,
                fillvalue=""
                if len(self.api_keys) < len(self.api_base_urls)
                else OPENAI_BASE_URL,
            )
            if (api_config := self.api_configs.get(base_url)) is None
            or api_config.enable
        ]


class RAGConfig(BaseModel):
    """RAG configuration."""

    class Web(BaseModel):
        """Web configuration."""

        class Search(BaseSettings):
            """Search configuration."""

            enable: Annotated[
                bool,
                Field(validation_alias=AliasChoices("ENABLE_RAG_WEB_SEARCH", "enable")),
            ] = True

        search: Search = Field(default_factory=Search)

    web: Web = Field(default_factory=Web)

    class File(BaseSettings, env_prefix="RAG_FILE_"):
        """File configuration."""

        max_count: int | None = None
        max_size: float | None = None
        """Max file size in MB"""

    file: File = Field(default_factory=File)


class TaskConfig(BaseModel):
    """Task configuration."""

    class AutoComplete(BaseSettings, env_prefix="AUTOCOMPLETE_GENERATION_"):
        """Auto-complete configuration."""

        enable: Annotated[
            bool,
            Field(
                validation_alias=AliasChoices(
                    "ENABLE_AUTOCOMPLETE_GENERATION", "enable"
                )
            ),
        ] = True
        input_max_length: int = -1
        prompt_template: str = Field(
            default_factory=lambda: (
                Path(__file__).parent / "templates" / "autocomplete.j2"
            ).read_text()
        )

    autocomplete: AutoComplete = Field(default_factory=AutoComplete)


class BannerModel(BaseModel):
    """Banner model."""

    id: str
    type: str
    title: Optional[str] = None
    content: str
    dismissible: bool
    timestamp: int


class UIConfig(BaseSettings):
    """UI configuration."""

    class PromptSuggestion(BaseModel):
        """Prompt suggestion model."""

        title: tuple[str, str]
        content: str

    default_locale: str = ""
    prompt_suggestions: list[PromptSuggestion] = Field(default_factory=list)
    enable_signup: bool = True
    default_models: str | None = None
    language_model_order_list: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("MODEL_ORDER_LIST", "language_model_order_list"),
        serialization_alias="model_order_list",
    )
    ENABLE_LOGIN_FORM: bool = True
    default_user_role: UserRole = "pending"
    enable_community_sharing: bool = True
    enable_message_rating: bool = True
    banners: list[BannerModel] = Field(
        default_factory=list, validation_alias=AliasChoices("WEBUI_BANNERS", "banners")
    )


class UserConfig(BaseModel):
    """User configuration."""

    class Permissions(BaseModel):
        """User permissions."""

        class Workspace(BaseSettings):
            """User workspace permissions."""

            models: Annotated[
                bool,
                Field(
                    validation_alias=AliasChoices(
                        "USER_PERMISSIONS_WORKSPACE_MODELS_ACCESS", "models"
                    )
                ),
            ] = True
            knowledge: Annotated[
                bool,
                Field(
                    validation_alias=AliasChoices(
                        "USER_PERMISSIONS_WORKSPACE_KNOWLEDGE_ACCESS", "knowledge"
                    )
                ),
            ] = True
            prompts: Annotated[
                bool,
                Field(
                    validation_alias=AliasChoices(
                        "USER_PERMISSIONS_WORKSPACE_PROMPTS_ACCESS", "prompts"
                    )
                ),
            ] = True
            tools: Annotated[
                bool,
                Field(
                    validation_alias=AliasChoices(
                        "USER_PERMISSIONS_WORKSPACE_TOOLS_ACCESS", "tools"
                    )
                ),
            ] = True

        workspace: Workspace = Field(default_factory=Workspace)

        class Chat(BaseSettings, env_prefix="USER_PERMISSIONS_CHAT_"):
            """User chat permissions."""

            file_upload: bool = True
            delete: bool = True
            edit: bool = True
            temporary: bool = True

        chat: Chat = Field(default_factory=Chat)

    permissions: Permissions = Field(default_factory=Permissions)


@deprecated("Backward compatibility with Open WebUI, will be removed >= 1.0")
class ConfigData(BaseModel, nested_model_default_partial_update=True):
    """Config data model."""

    version: int = 0
    audio: AudioConfig = Field(default_factory=AudioConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    evaluation: Evaluation = Field(default_factory=Evaluation)
    image_generation: ImageGenerationConfig = Field(
        default_factory=ImageGenerationConfig
    )
    ldap: LDAPConfig = Field(default_factory=LDAPConfig)
    oauth: OAuthConfig = Field(default_factory=OAuthConfig)
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)
    rag: RAGConfig = Field(default_factory=RAGConfig)
    task: TaskConfig = Field(default_factory=TaskConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    user: UserConfig = Field(default_factory=UserConfig)
    webhook_url: str = ""


class EndpointFilter(logging.Filter):
    """Filter out /health from the logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter out /health from the logs."""
        return record.getMessage().find("/health") == -1


logging.getLogger("uvicorn.access").addFilter(EndpointFilter())


class Config(SQLModel, table=True):
    """Config model."""

    id: int | None = SQLModelField(default=None, primary_key=True)
    data: ConfigData = SQLModelField(sa_type=ConfigData.as_sa_type(), nullable=False)
    version: int = 0
    created_at: datetime = SQLModelField(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime | None = SQLModelField(
        default=None, sa_column_kwargs=dict(onupdate=func.now())
    )


def load_json_config():
    """Load the JSON config."""
    return json.loads((env.DATA_DIR / "config.json").read_text())


def save_to_db(data):
    """Save the config to the database."""
    with get_db() as db:
        existing_config = db.query(Config).first()
        if not existing_config:
            new_config = Config(data=data, version=0)
            db.add(new_config)
        else:
            existing_config.data = data
            existing_config.updated_at = datetime.now(UTC)
            db.add(existing_config)
        db.commit()


def reset_config():
    """Reset the config."""
    with get_db() as db:
        db.query(Config).delete()
        db.commit()


if (env.DATA_DIR / "config.json").exists():
    data = load_json_config()
    save_to_db(data)
    os.rename(env.DATA_DIR / "config.json", env.DATA_DIR / "old_config.json")


def get_config():
    """Get the config."""
    with get_db() as db:
        config_entry = db.query(Config).order_by(col(Config.id).desc()).first()
        return config_entry.data.model_dump() if config_entry else {}


async def _get_config(session: SessionDep):
    return (await session.exec(select(Config).order_by(col(Config.id).desc()))).first()


ConfigDep = Annotated[
    ConfigData, Depends(lambda: ConfigData.model_validate(get_config()))
]
ConfigDBDep = Annotated[Config | None, Depends(_get_config)]


CONFIG_DATA = {}


def get_config_value(config_path: str):
    """Get the config value."""
    path_parts = config_path.split(".")
    cur_config = CONFIG_DATA
    for key in path_parts:
        if key in cur_config:
            cur_config = cur_config[key]
        else:
            return None
    return cur_config


PERSISTENT_CONFIG_REGISTRY = []


T = TypeVar("T")


class PersistentConfig(Generic[T]):
    """Persistent config class."""

    def __init__(self, env_name: str, config_path: str, env_value: T):
        """Initialize the class.

        Args:
            env_name (str): The environment variable name
            config_path (str): The config path
            env_value (T): The environment value

        """
        self.env_name = env_name
        self.config_path = config_path
        self.env_value = env_value
        self.config_value = get_config_value(config_path)
        if self.config_value is not None:
            logger.info(f"'{env_name}' loaded from the latest database entry")
            self.value = self.config_value
        else:
            self.value = env_value

        PERSISTENT_CONFIG_REGISTRY.append(self)

    def __str__(self):
        return str(self.value)

    def __getattribute__(self, item):
        if item == "__dict__":
            raise TypeError(
                "PersistentConfig object cannot be converted to dict, use config_get or .value instead."
            )
        return super().__getattribute__(item)

    def update(self):
        """Update the config."""
        new_value = get_config_value(self.config_path)
        if new_value is not None:
            self.value = new_value
            logger.info(f"Updated {self.env_name} to new value {self.value}")

    def save(self):
        """Save the config."""
        logger.info(f"Saving '{self.env_name}' to the database")
        path_parts = self.config_path.split(".")
        sub_config = CONFIG_DATA
        for key in path_parts[:-1]:
            if key not in sub_config:
                sub_config[key] = {}
            sub_config = sub_config[key]
        sub_config[path_parts[-1]] = self.value
        save_to_db(CONFIG_DATA)
        self.config_value = self.value


class AppConfig:
    """App config class."""

    _state: dict[str, PersistentConfig]

    def __init__(self):  # noqa: D107
        super().__setattr__("_state", {})

    def __setattr__(self, key, value):
        if isinstance(value, PersistentConfig):
            self._state[key] = value
        else:
            self._state[key].value = value
            self._state[key].save()

    def __getattr__(self, key):
        return self._state[key].value


STATIC_DIR = Path(os.getenv("STATIC_DIR", OPEN_WEBUI_DIR / "static")).resolve()

frontend_favicon = env.FRONTEND_BUILD_DIR / "static" / "favicon.png"

if frontend_favicon.exists():
    try:
        shutil.copyfile(frontend_favicon, STATIC_DIR / "favicon.png")
    except Exception as e:
        logger.error(f"An error occurred: {e}")
else:
    logger.warning(f"Frontend favicon not found at {frontend_favicon}")

frontend_splash = env.FRONTEND_BUILD_DIR / "static" / "splash.png"

if frontend_splash.exists():
    try:
        shutil.copyfile(frontend_splash, STATIC_DIR / "splash.png")
    except Exception as e:
        logger.error(f"An error occurred: {e}")
else:
    logger.warning(f"Frontend splash not found at {frontend_splash}")


STORAGE_PROVIDER = os.environ.get("STORAGE_PROVIDER", "")  # defaults to local, s3
S3_ACCESS_KEY_ID = os.environ.get("S3_ACCESS_KEY_ID", None)
S3_SECRET_ACCESS_KEY = os.environ.get("S3_SECRET_ACCESS_KEY", None)
S3_REGION_NAME = os.environ.get("S3_REGION_NAME", None)
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", None)
S3_ENDPOINT_URL = os.environ.get("S3_ENDPOINT_URL", None)


UPLOAD_DIR = env.DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

CACHE_DIR = env.DATA_DIR / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


ENABLE_OLLAMA_API = PersistentConfig(
    "ENABLE_OLLAMA_API",
    "ollama.enable",
    os.environ.get("ENABLE_OLLAMA_API", "True").lower() == "true",
)

OLLAMA_API_BASE_URL = os.environ.get(
    "OLLAMA_API_BASE_URL", "http://localhost:11434/api"
)

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "")
if OLLAMA_BASE_URL:
    # Remove trailing slash
    OLLAMA_BASE_URL = (
        OLLAMA_BASE_URL[:-1] if OLLAMA_BASE_URL.endswith("/") else OLLAMA_BASE_URL
    )


K8S_FLAG = os.environ.get("K8S_FLAG", "")
USE_OLLAMA_DOCKER = os.environ.get("USE_OLLAMA_DOCKER", "false")

if OLLAMA_BASE_URL == "" and OLLAMA_API_BASE_URL != "":
    OLLAMA_BASE_URL = (
        OLLAMA_API_BASE_URL[:-4]
        if OLLAMA_API_BASE_URL.endswith("/api")
        else OLLAMA_API_BASE_URL
    )

if env.WEBUI_ENV == "prod":
    if OLLAMA_BASE_URL == "/ollama" and not K8S_FLAG:
        if USE_OLLAMA_DOCKER.lower() == "true":
            # if you use all-in-one docker container (Open WebUI + Ollama)
            # with the docker build arg USE_OLLAMA=true (--build-arg="USE_OLLAMA=true") this only works with http://localhost:11434
            OLLAMA_BASE_URL = "http://localhost:11434"
        else:
            OLLAMA_BASE_URL = "http://host.docker.internal:11434"
    elif K8S_FLAG:
        OLLAMA_BASE_URL = "http://ollama-service.open-webui.svc.cluster.local:11434"


OLLAMA_BASE_URLS = os.environ.get("OLLAMA_BASE_URLS", "")
OLLAMA_BASE_URLS = OLLAMA_BASE_URLS if OLLAMA_BASE_URLS != "" else OLLAMA_BASE_URL

OLLAMA_BASE_URLS = [url.strip() for url in OLLAMA_BASE_URLS.split(";")]
OLLAMA_BASE_URLS = PersistentConfig(
    "OLLAMA_BASE_URLS", "ollama.base_urls", OLLAMA_BASE_URLS
)

OLLAMA_API_CONFIGS = PersistentConfig(
    "OLLAMA_API_CONFIGS",
    "ollama.api_configs",
    {},
)

OPENAI_API_KEY = env.OPENAI_API_KEY
OPENAI_API_BASE_URL = env.OPENAI_BASE_URL


OPENAI_API_KEYS = PersistentConfig(
    "OPENAI_API_KEYS", "openai.api_keys", env.OPENAI_API_KEYS
)

OPENAI_API_BASE_URLS = os.environ.get("OPENAI_API_BASE_URLS", "")
OPENAI_API_BASE_URLS = (
    OPENAI_API_BASE_URLS if OPENAI_API_BASE_URLS != "" else OPENAI_API_BASE_URL
)

OPENAI_API_BASE_URLS = [
    url.strip() if url != "" else OPENAI_BASE_URL
    for url in OPENAI_API_BASE_URLS.split(";")
]
OPENAI_API_BASE_URLS = PersistentConfig(
    "OPENAI_API_BASE_URLS", "openai.api_base_urls", OPENAI_API_BASE_URLS
)

OPENAI_API_CONFIGS = PersistentConfig(
    "OPENAI_API_CONFIGS",
    "openai.api_configs",
    {},
)

# Get the actual OpenAI API key based on the base URL
OPENAI_API_KEY = ""
try:
    OPENAI_API_KEY = OPENAI_API_KEYS.value[
        OPENAI_API_BASE_URLS.value.index(OPENAI_BASE_URL)  # type: ignore
    ]
except Exception:
    pass
OPENAI_API_BASE_URL = OPENAI_BASE_URL

WEBUI_URL = PersistentConfig(
    "WEBUI_URL", "webui.url", os.environ.get("WEBUI_URL", "http://localhost:3000")
)

ENABLE_LOGIN_FORM = PersistentConfig(
    "ENABLE_LOGIN_FORM",
    "ui.ENABLE_LOGIN_FORM",
    os.environ.get("ENABLE_LOGIN_FORM", "True").lower() == "true",
)


DEFAULT_LOCALE = PersistentConfig(
    "DEFAULT_LOCALE",
    "ui.default_locale",
    os.environ.get("DEFAULT_LOCALE", ""),
)

DEFAULT_MODELS = PersistentConfig(
    "DEFAULT_MODELS", "ui.default_models", os.environ.get("DEFAULT_MODELS", None)
)

DEFAULT_PROMPT_SUGGESTIONS = PersistentConfig(
    "DEFAULT_PROMPT_SUGGESTIONS",
    "ui.prompt_suggestions",
    [
        {
            "title": ["Help me study", "vocabulary for a college entrance exam"],
            "content": "Help me study vocabulary: write a sentence for me to fill in the blank, and I'll try to pick the correct option.",
        },
        {
            "title": ["Give me ideas", "for what to do with my kids' art"],
            "content": "What are 5 creative things I could do with my kids' art? I don't want to throw them away, but it's also so much clutter.",
        },
        {
            "title": ["Tell me a fun fact", "about the Roman Empire"],
            "content": "Tell me a random fun fact about the Roman Empire",
        },
        {
            "title": ["Show me a code snippet", "of a website's sticky header"],
            "content": "Show me a code snippet of a website's sticky header in CSS and JavaScript.",
        },
        {
            "title": [
                "Explain options trading",
                "if I'm familiar with buying and selling stocks",
            ],
            "content": "Explain options trading in simple terms if I'm familiar with buying and selling stocks.",
        },
        {
            "title": ["Overcome procrastination", "give me tips"],
            "content": "Could you start by asking me about instances when I procrastinate the most and then give me some suggestions to overcome it?",
        },
    ],
)

USER_PERMISSIONS_WORKSPACE_MODELS_ACCESS = (
    os.environ.get("USER_PERMISSIONS_WORKSPACE_MODELS_ACCESS", "False").lower()
    == "true"
)

USER_PERMISSIONS_WORKSPACE_KNOWLEDGE_ACCESS = (
    os.environ.get("USER_PERMISSIONS_WORKSPACE_KNOWLEDGE_ACCESS", "False").lower()
    == "true"
)

USER_PERMISSIONS_WORKSPACE_PROMPTS_ACCESS = (
    os.environ.get("USER_PERMISSIONS_WORKSPACE_PROMPTS_ACCESS", "False").lower()
    == "true"
)

USER_PERMISSIONS_WORKSPACE_TOOLS_ACCESS = (
    os.environ.get("USER_PERMISSIONS_WORKSPACE_TOOLS_ACCESS", "False").lower() == "true"
)

USER_PERMISSIONS_CHAT_FILE_UPLOAD = (
    os.environ.get("USER_PERMISSIONS_CHAT_FILE_UPLOAD", "True").lower() == "true"
)

USER_PERMISSIONS_CHAT_DELETE = (
    os.environ.get("USER_PERMISSIONS_CHAT_DELETE", "True").lower() == "true"
)

USER_PERMISSIONS_CHAT_EDIT = (
    os.environ.get("USER_PERMISSIONS_CHAT_EDIT", "True").lower() == "true"
)

USER_PERMISSIONS_CHAT_TEMPORARY = (
    os.environ.get("USER_PERMISSIONS_CHAT_TEMPORARY", "True").lower() == "true"
)

USER_PERMISSIONS = PersistentConfig(
    "USER_PERMISSIONS",
    "user.permissions",
    {
        "workspace": {
            "models": USER_PERMISSIONS_WORKSPACE_MODELS_ACCESS,
            "knowledge": USER_PERMISSIONS_WORKSPACE_KNOWLEDGE_ACCESS,
            "prompts": USER_PERMISSIONS_WORKSPACE_PROMPTS_ACCESS,
            "tools": USER_PERMISSIONS_WORKSPACE_TOOLS_ACCESS,
        },
        "chat": {
            "file_upload": USER_PERMISSIONS_CHAT_FILE_UPLOAD,
            "delete": USER_PERMISSIONS_CHAT_DELETE,
            "edit": USER_PERMISSIONS_CHAT_EDIT,
            "temporary": USER_PERMISSIONS_CHAT_TEMPORARY,
        },
    },
)

ENABLE_CHANNELS = PersistentConfig(
    "ENABLE_CHANNELS",
    "channels.enable",
    os.environ.get("ENABLE_CHANNELS", "False").lower() == "true",
)


ENABLE_EVALUATION_ARENA_MODELS = PersistentConfig(
    "ENABLE_EVALUATION_ARENA_MODELS",
    "evaluation.arena.enable",
    os.environ.get("ENABLE_EVALUATION_ARENA_MODELS", "True").lower() == "true",
)
EVALUATION_ARENA_MODELS = PersistentConfig(
    "EVALUATION_ARENA_MODELS",
    "evaluation.arena.models",
    [],
)

DEFAULT_ARENA_MODEL = {
    "id": "arena-model",
    "name": "Arena Model",
    "meta": {
        "profile_image_url": "/favicon.png",
        "description": "Submit your questions to anonymous AI chatbots and vote on the best response.",
        "model_ids": None,
    },
}

ENABLE_ADMIN_EXPORT = os.environ.get("ENABLE_ADMIN_EXPORT", "True").lower() == "true"

ENABLE_ADMIN_CHAT_ACCESS = (
    os.environ.get("ENABLE_ADMIN_CHAT_ACCESS", "True").lower() == "true"
)

ENABLE_COMMUNITY_SHARING = PersistentConfig(
    "ENABLE_COMMUNITY_SHARING",
    "ui.enable_community_sharing",
    os.environ.get("ENABLE_COMMUNITY_SHARING", "True").lower() == "true",
)

ENABLE_MESSAGE_RATING = PersistentConfig(
    "ENABLE_MESSAGE_RATING",
    "ui.enable_message_rating",
    os.environ.get("ENABLE_MESSAGE_RATING", "True").lower() == "true",
)


def validate_cors_origins(origins: list[str]):
    """Validate the CORS origins."""
    for origin in origins:
        if origin != "*":
            validate_cors_origin(origin)


def validate_cors_origin(origin: str):
    """Validate the CORS origin."""
    parsed_url = urlparse(origin)

    # Check if the scheme is either http or https
    if parsed_url.scheme not in ["http", "https"]:
        raise ValueError(
            f"Invalid scheme in CORS_ALLOW_ORIGIN: '{origin}'. Only 'http' and 'https' are allowed."
        )

    # Ensure that the netloc (domain + port) is present, indicating it's a valid URL
    if not parsed_url.netloc:
        raise ValueError(f"Invalid URL structure in CORS_ALLOW_ORIGIN: '{origin}'.")


# For production, you should only need one host as
# fastapi serves the svelte-kit built frontend and backend from the same host and port.
# To test CORS_ALLOW_ORIGIN locally, you can set something like
# CORS_ALLOW_ORIGIN=http://localhost:5173;http://localhost:8080
# in your .env file depending on your frontend port, 5173 in this case.
CORS_ALLOW_ORIGIN = os.environ.get("CORS_ALLOW_ORIGIN", "*").split(";")

if "*" in CORS_ALLOW_ORIGIN:
    logger.warning(
        "\n\nWARNING: CORS_ALLOW_ORIGIN IS SET TO '*' - NOT RECOMMENDED FOR PRODUCTION DEPLOYMENTS.\n"
    )

validate_cors_origins(CORS_ALLOW_ORIGIN)

SHOW_ADMIN_DETAILS = PersistentConfig(
    "SHOW_ADMIN_DETAILS",
    "auth.admin.show",
    os.environ.get("SHOW_ADMIN_DETAILS", "true").lower() == "true",
)

ADMIN_EMAIL = PersistentConfig(
    "ADMIN_EMAIL",
    "auth.admin.email",
    os.environ.get("ADMIN_EMAIL", None),
)

TASK_MODEL = PersistentConfig(
    "TASK_MODEL",
    "task.model.default",
    os.environ.get("TASK_MODEL", ""),
)

TASK_MODEL_EXTERNAL = PersistentConfig(
    "TASK_MODEL_EXTERNAL",
    "task.model.external",
    os.environ.get("TASK_MODEL_EXTERNAL", ""),
)

TITLE_GENERATION_PROMPT_TEMPLATE = PersistentConfig(
    "TITLE_GENERATION_PROMPT_TEMPLATE",
    "task.title.prompt_template",
    os.environ.get("TITLE_GENERATION_PROMPT_TEMPLATE", ""),
)

DEFAULT_TITLE_GENERATION_PROMPT_TEMPLATE = """Create a concise, 3-5 word title with an emoji as a title for the chat history, in the given language. Suitable Emojis for the summary can be used to enhance understanding but avoid quotation marks or special formatting. RESPOND ONLY WITH THE TITLE TEXT.

Examples of titles:
📉 Stock Market Trends
🍪 Perfect Chocolate Chip Recipe
Evolution of Music Streaming
Remote Work Productivity Tips
Artificial Intelligence in Healthcare
🎮 Video Game Development Insights

<chat_history>
{{MESSAGES:END:2}}
</chat_history>"""


TAGS_GENERATION_PROMPT_TEMPLATE = PersistentConfig(
    "TAGS_GENERATION_PROMPT_TEMPLATE",
    "task.tags.prompt_template",
    os.environ.get("TAGS_GENERATION_PROMPT_TEMPLATE", ""),
)

DEFAULT_TAGS_GENERATION_PROMPT_TEMPLATE = """### Task:
Generate 1-3 broad tags categorizing the main themes of the chat history, along with 1-3 more specific subtopic tags.

### Guidelines:
- Start with high-level domains (e.g. Science, Technology, Philosophy, Arts, Politics, Business, Health, Sports, Entertainment, Education)
- Consider including relevant subfields/subdomains if they are strongly represented throughout the conversation
- If content is too short (less than 3 messages) or too diverse, use only ["General"]
- Use the chat's primary language; default to English if multilingual
- Prioritize accuracy over specificity

### Output:
JSON format: { "tags": ["tag1", "tag2", "tag3"] }

### Chat History:
<chat_history>
{{MESSAGES:END:6}}
</chat_history>"""

ENABLE_TAGS_GENERATION = PersistentConfig(
    "ENABLE_TAGS_GENERATION",
    "task.tags.enable",
    os.environ.get("ENABLE_TAGS_GENERATION", "True").lower() == "true",
)


ENABLE_SEARCH_QUERY_GENERATION = PersistentConfig(
    "ENABLE_SEARCH_QUERY_GENERATION",
    "task.query.search.enable",
    os.environ.get("ENABLE_SEARCH_QUERY_GENERATION", "True").lower() == "true",
)

ENABLE_RETRIEVAL_QUERY_GENERATION = PersistentConfig(
    "ENABLE_RETRIEVAL_QUERY_GENERATION",
    "task.query.retrieval.enable",
    os.environ.get("ENABLE_RETRIEVAL_QUERY_GENERATION", "True").lower() == "true",
)


QUERY_GENERATION_PROMPT_TEMPLATE = PersistentConfig(
    "QUERY_GENERATION_PROMPT_TEMPLATE",
    "task.query.prompt_template",
    os.environ.get("QUERY_GENERATION_PROMPT_TEMPLATE", ""),
)

DEFAULT_QUERY_GENERATION_PROMPT_TEMPLATE = """### Task:
Analyze the chat history to determine the necessity of generating search queries, in the given language. By default, **prioritize generating 1-3 broad and relevant search queries** unless it is absolutely certain that no additional information is required. The aim is to retrieve comprehensive, updated, and valuable information even with minimal uncertainty. If no search is unequivocally needed, return an empty list.

### Guidelines:
- Respond **EXCLUSIVELY** with a JSON object. Any form of extra commentary, explanation, or additional text is strictly prohibited.
- When generating search queries, respond in the format: { "queries": ["query1", "query2"] }, ensuring each query is distinct, concise, and relevant to the topic.
- If and only if it is entirely certain that no useful results can be retrieved by a search, return: { "queries": [] }.
- Err on the side of suggesting search queries if there is **any chance** they might provide useful or updated information.
- Be concise and focused on composing high-quality search queries, avoiding unnecessary elaboration, commentary, or assumptions.
- Today's date is: {{CURRENT_DATE}}.
- Always prioritize providing actionable and broad queries that maximize informational coverage.

### Output:
Strictly return in JSON format:
{
  "queries": ["query1", "query2"]
}

### Chat History:
<chat_history>
{{MESSAGES:END:6}}
</chat_history>
"""

TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE = PersistentConfig(
    "TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE",
    "task.tools.prompt_template",
    os.environ.get("TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE", ""),
)


DEFAULT_TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE = """Available Tools: {{TOOLS}}\nReturn an empty string if no tools match the query. If a function tool matches, construct and return a JSON object in the format {\"name\": \"functionName\", \"parameters\": {\"requiredFunctionParamKey\": \"requiredFunctionParamValue\"}} using the appropriate tool and its parameters. Only return the object and limit the response to the JSON object without additional text."""


DEFAULT_EMOJI_GENERATION_PROMPT_TEMPLATE = """Your task is to reflect the speaker's likely facial expression through a fitting emoji. Interpret emotions from the message and reflect their facial expression using fitting, diverse emojis (e.g., 😊, 😢, 😡, 😱).

Message: ```{{prompt}}```"""

DEFAULT_MOA_GENERATION_PROMPT_TEMPLATE = """You have been provided with a set of responses from various models to the latest user query: "{{prompt}}"

Your task is to synthesize these responses into a single, high-quality response. It is crucial to critically evaluate the information provided in these responses, recognizing that some of it may be biased or incorrect. Your response should not simply replicate the given answers but should offer a refined, accurate, and comprehensive reply to the instruction. Ensure your response is well-structured, coherent, and adheres to the highest standards of accuracy and reliability.

Responses from models: {{responses}}"""

####################################
# Vector Database
####################################

VECTOR_DB = os.environ.get("VECTOR_DB", "chroma")

# Chroma
CHROMA_DATA_PATH = str(env.DATA_DIR / "vector_db")
CHROMA_TENANT = os.environ.get("CHROMA_TENANT", chromadb.config.DEFAULT_TENANT)
CHROMA_DATABASE = os.environ.get("CHROMA_DATABASE", chromadb.config.DEFAULT_DATABASE)
CHROMA_HTTP_HOST = os.environ.get("CHROMA_HTTP_HOST", "")
CHROMA_HTTP_PORT = int(os.environ.get("CHROMA_HTTP_PORT", "8000"))
CHROMA_CLIENT_AUTH_PROVIDER = os.environ.get("CHROMA_CLIENT_AUTH_PROVIDER", "")
CHROMA_CLIENT_AUTH_CREDENTIALS = os.environ.get("CHROMA_CLIENT_AUTH_CREDENTIALS", "")
# Comma-separated list of header=value pairs
CHROMA_HTTP_HEADERS = os.environ.get("CHROMA_HTTP_HEADERS", "")
if CHROMA_HTTP_HEADERS:
    CHROMA_HTTP_HEADERS = dict(
        [pair.split("=") for pair in CHROMA_HTTP_HEADERS.split(",")]
    )
else:
    CHROMA_HTTP_HEADERS = None
CHROMA_HTTP_SSL = os.environ.get("CHROMA_HTTP_SSL", "false").lower() == "true"
# this uses the model defined in the Dockerfile ENV variable. If you dont use docker or docker based deployments such as k8s, the default embedding model will be used (sentence-transformers/all-MiniLM-L6-v2)

# Milvus

MILVUS_URI = os.environ.get("MILVUS_URI", str(env.DATA_DIR / "vector_db" / "milvus.db"))

# Qdrant
QDRANT_URI = os.environ.get("QDRANT_URI", None)
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY", None)

# OpenSearch
OPENSEARCH_URI = os.environ.get("OPENSEARCH_URI", "https://localhost:9200")
OPENSEARCH_SSL = os.environ.get("OPENSEARCH_SSL", True)
OPENSEARCH_CERT_VERIFY = os.environ.get("OPENSEARCH_CERT_VERIFY", False)
OPENSEARCH_USERNAME = os.environ.get("OPENSEARCH_USERNAME", None)
OPENSEARCH_PASSWORD = os.environ.get("OPENSEARCH_PASSWORD", None)

# Pgvector
PGVECTOR_DB_URL = os.environ.get("PGVECTOR_DB_URL", DATABASE_URL)
if VECTOR_DB == "pgvector" and not PGVECTOR_DB_URL.startswith("postgres"):
    raise ValueError(
        "Pgvector requires setting PGVECTOR_DB_URL or using Postgres with vector extension as the primary database."
    )
PGVECTOR_INITIALIZE_MAX_VECTOR_LENGTH = int(
    os.environ.get("PGVECTOR_INITIALIZE_MAX_VECTOR_LENGTH", "1536")
)

# If configured, Google Drive will be available as an upload option.
ENABLE_GOOGLE_DRIVE_INTEGRATION = PersistentConfig(
    "ENABLE_GOOGLE_DRIVE_INTEGRATION",
    "google_drive.enable",
    os.getenv("ENABLE_GOOGLE_DRIVE_INTEGRATION", "False").lower() == "true",
)

GOOGLE_DRIVE_CLIENT_ID = PersistentConfig(
    "GOOGLE_DRIVE_CLIENT_ID",
    "google_drive.client_id",
    os.environ.get("GOOGLE_DRIVE_CLIENT_ID", ""),
)

GOOGLE_DRIVE_API_KEY = PersistentConfig(
    "GOOGLE_DRIVE_API_KEY",
    "google_drive.api_key",
    os.environ.get("GOOGLE_DRIVE_API_KEY", ""),
)

# RAG Content Extraction
CONTENT_EXTRACTION_ENGINE = PersistentConfig(
    "CONTENT_EXTRACTION_ENGINE",
    "rag.CONTENT_EXTRACTION_ENGINE",
    os.environ.get("CONTENT_EXTRACTION_ENGINE", "").lower(),
)

TIKA_SERVER_URL = PersistentConfig(
    "TIKA_SERVER_URL",
    "rag.tika_server_url",
    os.getenv("TIKA_SERVER_URL", "http://tika:9998"),  # Default for sidecar deployment
)

RAG_TOP_K = PersistentConfig(
    "RAG_TOP_K", "rag.top_k", int(os.environ.get("RAG_TOP_K", "3"))
)
RAG_RELEVANCE_THRESHOLD = PersistentConfig(
    "RAG_RELEVANCE_THRESHOLD",
    "rag.relevance_threshold",
    float(os.environ.get("RAG_RELEVANCE_THRESHOLD", "0.0")),
)

ENABLE_RAG_HYBRID_SEARCH = PersistentConfig(
    "ENABLE_RAG_HYBRID_SEARCH",
    "rag.enable_hybrid_search",
    os.environ.get("ENABLE_RAG_HYBRID_SEARCH", "").lower() == "true",
)

RAG_FILE_MAX_COUNT = PersistentConfig(
    "RAG_FILE_MAX_COUNT",
    "rag.file.max_count",
    int(count) if (count := os.getenv("RAG_FILE_MAX_COUNT")) else None,
)

RAG_FILE_MAX_SIZE = PersistentConfig(
    "RAG_FILE_MAX_SIZE",
    "rag.file.max_size",
    int(size) if (size := os.getenv("RAG_FILE_MAX_SIZE")) else None,
)

ENABLE_RAG_WEB_LOADER_SSL_VERIFICATION = PersistentConfig(
    "ENABLE_RAG_WEB_LOADER_SSL_VERIFICATION",
    "rag.enable_web_loader_ssl_verification",
    os.environ.get("ENABLE_RAG_WEB_LOADER_SSL_VERIFICATION", "True").lower() == "true",
)

RAG_EMBEDDING_ENGINE = PersistentConfig(
    "RAG_EMBEDDING_ENGINE",
    "rag.embedding_engine",
    os.environ.get("RAG_EMBEDDING_ENGINE", ""),
)

PDF_EXTRACT_IMAGES = PersistentConfig(
    "PDF_EXTRACT_IMAGES",
    "rag.pdf_extract_images",
    os.environ.get("PDF_EXTRACT_IMAGES", "False").lower() == "true",
)

RAG_EMBEDDING_MODEL = PersistentConfig(
    "RAG_EMBEDDING_MODEL",
    "rag.embedding_model",
    os.environ.get("RAG_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
)
logger.info(f"Embedding model set: {RAG_EMBEDDING_MODEL.value}")

RAG_EMBEDDING_MODEL_AUTO_UPDATE = (
    not OFFLINE_MODE
    and os.environ.get("RAG_EMBEDDING_MODEL_AUTO_UPDATE", "True").lower() == "true"
)

RAG_EMBEDDING_MODEL_TRUST_REMOTE_CODE = (
    os.environ.get("RAG_EMBEDDING_MODEL_TRUST_REMOTE_CODE", "True").lower() == "true"
)

RAG_EMBEDDING_BATCH_SIZE = PersistentConfig(
    "RAG_EMBEDDING_BATCH_SIZE",
    "rag.embedding_batch_size",
    int(
        os.environ.get("RAG_EMBEDDING_BATCH_SIZE")
        or os.environ.get("RAG_EMBEDDING_OPENAI_BATCH_SIZE", "1")
    ),
)

RAG_RERANKING_MODEL = PersistentConfig(
    "RAG_RERANKING_MODEL",
    "rag.reranking_model",
    os.environ.get("RAG_RERANKING_MODEL", ""),
)
if RAG_RERANKING_MODEL.value != "":
    logger.info(f"Reranking model set: {RAG_RERANKING_MODEL.value}")

RAG_RERANKING_MODEL_AUTO_UPDATE = (
    not OFFLINE_MODE
    and os.environ.get("RAG_RERANKING_MODEL_AUTO_UPDATE", "True").lower() == "true"
)

RAG_RERANKING_MODEL_TRUST_REMOTE_CODE = (
    os.environ.get("RAG_RERANKING_MODEL_TRUST_REMOTE_CODE", "True").lower() == "true"
)


RAG_TEXT_SPLITTER = PersistentConfig(
    "RAG_TEXT_SPLITTER",
    "rag.text_splitter",
    os.environ.get("RAG_TEXT_SPLITTER", ""),
)


TIKTOKEN_CACHE_DIR = os.environ.get("TIKTOKEN_CACHE_DIR", f"{CACHE_DIR}/tiktoken")
TIKTOKEN_ENCODING_NAME = PersistentConfig(
    "TIKTOKEN_ENCODING_NAME",
    "rag.tiktoken_encoding_name",
    os.environ.get("TIKTOKEN_ENCODING_NAME", "cl100k_base"),
)


CHUNK_SIZE = PersistentConfig(
    "CHUNK_SIZE", "rag.chunk_size", int(os.environ.get("CHUNK_SIZE", "1000"))
)
CHUNK_OVERLAP = PersistentConfig(
    "CHUNK_OVERLAP",
    "rag.chunk_overlap",
    int(os.environ.get("CHUNK_OVERLAP", "100")),
)

DEFAULT_RAG_TEMPLATE = """### Task:
Respond to the user query using the provided context, incorporating inline citations in the format [source_id] **only when the <source_id> tag is explicitly provided** in the context.

### Guidelines:
- If you don't know the answer, clearly state that.
- If uncertain, ask the user for clarification.
- Respond in the same language as the user's query.
- If the context is unreadable or of poor quality, inform the user and provide the best possible answer.
- If the answer isn't present in the context but you possess the knowledge, explain this to the user and provide the answer using your own understanding.
- **Only include inline citations using [source_id] when a <source_id> tag is explicitly provided in the context.**
- Do not cite if the <source_id> tag is not provided in the context.
- Do not use XML tags in your response.
- Ensure citations are concise and directly related to the information provided.

### Example of Citation:
If the user asks about a specific topic and the information is found in "whitepaper.pdf" with a provided <source_id>, the response should include the citation like so:
* "According to the study, the proposed method increases efficiency by 20% [whitepaper.pdf]."
If no <source_id> is present, the response should omit the citation.

### Output:
Provide a clear and direct response to the user's query, including inline citations in the format [source_id] only when the <source_id> tag is present in the context.

<context>
{{CONTEXT}}
</context>

<user_query>
{{QUERY}}
</user_query>
"""

RAG_TEMPLATE = PersistentConfig(
    "RAG_TEMPLATE",
    "rag.template",
    os.environ.get("RAG_TEMPLATE", DEFAULT_RAG_TEMPLATE),
)

RAG_OPENAI_API_BASE_URL = PersistentConfig(
    "RAG_OPENAI_API_BASE_URL",
    "rag.openai_api_base_url",
    os.getenv("RAG_OPENAI_API_BASE_URL", OPENAI_API_BASE_URL),
)
RAG_OPENAI_API_KEY = PersistentConfig(
    "RAG_OPENAI_API_KEY",
    "rag.openai_api_key",
    os.getenv("RAG_OPENAI_API_KEY", OPENAI_API_KEY),
)

RAG_OLLAMA_BASE_URL = PersistentConfig(
    "RAG_OLLAMA_BASE_URL",
    "rag.ollama.url",
    os.getenv("RAG_OLLAMA_BASE_URL", OLLAMA_BASE_URL),
)

RAG_OLLAMA_API_KEY = PersistentConfig(
    "RAG_OLLAMA_API_KEY",
    "rag.ollama.key",
    os.getenv("RAG_OLLAMA_API_KEY", ""),
)


ENABLE_RAG_LOCAL_WEB_FETCH = (
    os.getenv("ENABLE_RAG_LOCAL_WEB_FETCH", "False").lower() == "true"
)

YOUTUBE_LOADER_LANGUAGE = PersistentConfig(
    "YOUTUBE_LOADER_LANGUAGE",
    "rag.youtube_loader_language",
    os.getenv("YOUTUBE_LOADER_LANGUAGE", "en").split(","),
)

YOUTUBE_LOADER_PROXY_URL = PersistentConfig(
    "YOUTUBE_LOADER_PROXY_URL",
    "rag.youtube_loader_proxy_url",
    os.getenv("YOUTUBE_LOADER_PROXY_URL", ""),
)


ENABLE_RAG_WEB_SEARCH = PersistentConfig(
    "ENABLE_RAG_WEB_SEARCH",
    "rag.web.search.enable",
    os.getenv("ENABLE_RAG_WEB_SEARCH", "False").lower() == "true",
)

RAG_WEB_SEARCH_ENGINE = PersistentConfig(
    "RAG_WEB_SEARCH_ENGINE",
    "rag.web.search.engine",
    os.getenv("RAG_WEB_SEARCH_ENGINE", ""),
)

# You can provide a list of your own websites to filter after performing a web search.
# This ensures the highest level of safety and reliability of the information sources.
RAG_WEB_SEARCH_DOMAIN_FILTER_LIST = PersistentConfig(
    "RAG_WEB_SEARCH_DOMAIN_FILTER_LIST",
    "rag.rag.web.search.domain.filter_list",
    [
        # "wikipedia.com",
        # "wikimedia.org",
        # "wikidata.org",
    ],
)


SEARXNG_QUERY_URL = PersistentConfig(
    "SEARXNG_QUERY_URL",
    "rag.web.search.searxng_query_url",
    os.getenv("SEARXNG_QUERY_URL", ""),
)

GOOGLE_PSE_API_KEY = PersistentConfig(
    "GOOGLE_PSE_API_KEY",
    "rag.web.search.google_pse_api_key",
    os.getenv("GOOGLE_PSE_API_KEY", ""),
)

GOOGLE_PSE_ENGINE_ID = PersistentConfig(
    "GOOGLE_PSE_ENGINE_ID",
    "rag.web.search.google_pse_engine_id",
    os.getenv("GOOGLE_PSE_ENGINE_ID", ""),
)

BRAVE_SEARCH_API_KEY = PersistentConfig(
    "BRAVE_SEARCH_API_KEY",
    "rag.web.search.brave_search_api_key",
    os.getenv("BRAVE_SEARCH_API_KEY", ""),
)

KAGI_SEARCH_API_KEY = PersistentConfig(
    "KAGI_SEARCH_API_KEY",
    "rag.web.search.kagi_search_api_key",
    os.getenv("KAGI_SEARCH_API_KEY", ""),
)

MOJEEK_SEARCH_API_KEY = PersistentConfig(
    "MOJEEK_SEARCH_API_KEY",
    "rag.web.search.mojeek_search_api_key",
    os.getenv("MOJEEK_SEARCH_API_KEY", ""),
)

SERPSTACK_API_KEY = PersistentConfig(
    "SERPSTACK_API_KEY",
    "rag.web.search.serpstack_api_key",
    os.getenv("SERPSTACK_API_KEY", ""),
)

SERPSTACK_HTTPS = PersistentConfig(
    "SERPSTACK_HTTPS",
    "rag.web.search.serpstack_https",
    os.getenv("SERPSTACK_HTTPS", "True").lower() == "true",
)

SERPER_API_KEY = PersistentConfig(
    "SERPER_API_KEY",
    "rag.web.search.serper_api_key",
    os.getenv("SERPER_API_KEY", ""),
)

SERPLY_API_KEY = PersistentConfig(
    "SERPLY_API_KEY",
    "rag.web.search.serply_api_key",
    os.getenv("SERPLY_API_KEY", ""),
)

TAVILY_API_KEY = PersistentConfig(
    "TAVILY_API_KEY",
    "rag.web.search.tavily_api_key",
    os.getenv("TAVILY_API_KEY", ""),
)

JINA_API_KEY = PersistentConfig(
    "JINA_API_KEY",
    "rag.web.search.jina_api_key",
    os.getenv("JINA_API_KEY", ""),
)

SEARCHAPI_API_KEY = PersistentConfig(
    "SEARCHAPI_API_KEY",
    "rag.web.search.searchapi_api_key",
    os.getenv("SEARCHAPI_API_KEY", ""),
)

SEARCHAPI_ENGINE = PersistentConfig(
    "SEARCHAPI_ENGINE",
    "rag.web.search.searchapi_engine",
    os.getenv("SEARCHAPI_ENGINE", ""),
)

BING_SEARCH_V7_ENDPOINT = PersistentConfig(
    "BING_SEARCH_V7_ENDPOINT",
    "rag.web.search.bing_search_v7_endpoint",
    os.environ.get(
        "BING_SEARCH_V7_ENDPOINT", "https://api.bing.microsoft.com/v7.0/search"
    ),
)

BING_SEARCH_V7_SUBSCRIPTION_KEY = PersistentConfig(
    "BING_SEARCH_V7_SUBSCRIPTION_KEY",
    "rag.web.search.bing_search_v7_subscription_key",
    os.environ.get("BING_SEARCH_V7_SUBSCRIPTION_KEY", ""),
)


RAG_WEB_SEARCH_RESULT_COUNT = PersistentConfig(
    "RAG_WEB_SEARCH_RESULT_COUNT",
    "rag.web.search.result_count",
    int(os.getenv("RAG_WEB_SEARCH_RESULT_COUNT", "3")),
)

RAG_WEB_SEARCH_CONCURRENT_REQUESTS = PersistentConfig(
    "RAG_WEB_SEARCH_CONCURRENT_REQUESTS",
    "rag.web.search.concurrent_requests",
    int(os.getenv("RAG_WEB_SEARCH_CONCURRENT_REQUESTS", "10")),
)


####################################
# Images
####################################

IMAGE_GENERATION_ENGINE = PersistentConfig(
    "IMAGE_GENERATION_ENGINE",
    "image_generation.engine",
    os.getenv("IMAGE_GENERATION_ENGINE", "openai"),
)

ENABLE_IMAGE_GENERATION = PersistentConfig(
    "ENABLE_IMAGE_GENERATION",
    "image_generation.enable",
    os.environ.get("ENABLE_IMAGE_GENERATION", "").lower() == "true",
)
AUTOMATIC1111_BASE_URL = PersistentConfig(
    "AUTOMATIC1111_BASE_URL",
    "image_generation.automatic1111.base_url",
    os.getenv("AUTOMATIC1111_BASE_URL", ""),
)
AUTOMATIC1111_API_AUTH = PersistentConfig(
    "AUTOMATIC1111_API_AUTH",
    "image_generation.automatic1111.api_auth",
    os.getenv("AUTOMATIC1111_API_AUTH", ""),
)

AUTOMATIC1111_CFG_SCALE = PersistentConfig(
    "AUTOMATIC1111_CFG_SCALE",
    "image_generation.automatic1111.cfg_scale",
    float(scale) if (scale := os.getenv("AUTOMATIC1111_CFG_SCALE")) else None,
)


AUTOMATIC1111_SAMPLER = PersistentConfig(
    "AUTOMATIC1111_SAMPLER",
    "image_generation.automatic1111.sampler",
    (
        os.environ.get("AUTOMATIC1111_SAMPLER")
        if os.environ.get("AUTOMATIC1111_SAMPLER")
        else None
    ),
)

AUTOMATIC1111_SCHEDULER = PersistentConfig(
    "AUTOMATIC1111_SCHEDULER",
    "image_generation.automatic1111.scheduler",
    (
        os.environ.get("AUTOMATIC1111_SCHEDULER")
        if os.environ.get("AUTOMATIC1111_SCHEDULER")
        else None
    ),
)

COMFYUI_BASE_URL = PersistentConfig(
    "COMFYUI_BASE_URL",
    "image_generation.comfyui.base_url",
    os.getenv("COMFYUI_BASE_URL", ""),
)

COMFYUI_API_KEY = PersistentConfig(
    "COMFYUI_API_KEY",
    "image_generation.comfyui.api_key",
    os.getenv("COMFYUI_API_KEY", ""),
)

COMFYUI_DEFAULT_WORKFLOW = """
{
  "3": {
    "inputs": {
      "seed": 0,
      "steps": 20,
      "cfg": 8,
      "sampler_name": "euler",
      "scheduler": "normal",
      "denoise": 1,
      "model": [
        "4",
        0
      ],
      "positive": [
        "6",
        0
      ],
      "negative": [
        "7",
        0
      ],
      "latent_image": [
        "5",
        0
      ]
    },
    "class_type": "KSampler",
    "_meta": {
      "title": "KSampler"
    }
  },
  "4": {
    "inputs": {
      "ckpt_name": "model.safetensors"
    },
    "class_type": "CheckpointLoaderSimple",
    "_meta": {
      "title": "Load Checkpoint"
    }
  },
  "5": {
    "inputs": {
      "width": 512,
      "height": 512,
      "batch_size": 1
    },
    "class_type": "EmptyLatentImage",
    "_meta": {
      "title": "Empty Latent Image"
    }
  },
  "6": {
    "inputs": {
      "text": "Prompt",
      "clip": [
        "4",
        1
      ]
    },
    "class_type": "CLIPTextEncode",
    "_meta": {
      "title": "CLIP Text Encode (Prompt)"
    }
  },
  "7": {
    "inputs": {
      "text": "",
      "clip": [
        "4",
        1
      ]
    },
    "class_type": "CLIPTextEncode",
    "_meta": {
      "title": "CLIP Text Encode (Prompt)"
    }
  },
  "8": {
    "inputs": {
      "samples": [
        "3",
        0
      ],
      "vae": [
        "4",
        2
      ]
    },
    "class_type": "VAEDecode",
    "_meta": {
      "title": "VAE Decode"
    }
  },
  "9": {
    "inputs": {
      "filename_prefix": "ComfyUI",
      "images": [
        "8",
        0
      ]
    },
    "class_type": "SaveImage",
    "_meta": {
      "title": "Save Image"
    }
  }
}
"""


COMFYUI_WORKFLOW = PersistentConfig(
    "COMFYUI_WORKFLOW",
    "image_generation.comfyui.workflow",
    os.getenv("COMFYUI_WORKFLOW", COMFYUI_DEFAULT_WORKFLOW),
)

COMFYUI_WORKFLOW_NODES = PersistentConfig(
    "COMFYUI_WORKFLOW",
    "image_generation.comfyui.nodes",
    [],
)

IMAGES_OPENAI_API_BASE_URL = PersistentConfig(
    "IMAGES_OPENAI_API_BASE_URL",
    "image_generation.openai.api_base_url",
    os.getenv("IMAGES_OPENAI_API_BASE_URL", OPENAI_API_BASE_URL),
)
IMAGES_OPENAI_API_KEY = PersistentConfig(
    "IMAGES_OPENAI_API_KEY",
    "image_generation.openai.api_key",
    os.getenv("IMAGES_OPENAI_API_KEY", OPENAI_API_KEY),
)

IMAGE_SIZE = PersistentConfig(
    "IMAGE_SIZE", "image_generation.size", os.getenv("IMAGE_SIZE", "512x512")
)

IMAGE_STEPS = PersistentConfig(
    "IMAGE_STEPS", "image_generation.steps", int(os.getenv("IMAGE_STEPS", 50))
)

IMAGE_GENERATION_MODEL = PersistentConfig(
    "IMAGE_GENERATION_MODEL",
    "image_generation.model",
    os.getenv("IMAGE_GENERATION_MODEL", ""),
)

WHISPER_MODEL = PersistentConfig(
    "WHISPER_MODEL",
    "audio.stt.whisper_model",
    os.getenv("WHISPER_MODEL", "base"),
)

WHISPER_MODEL_DIR = os.getenv("WHISPER_MODEL_DIR", f"{CACHE_DIR}/whisper/models")
WHISPER_MODEL_AUTO_UPDATE = (
    not OFFLINE_MODE
    and os.environ.get("WHISPER_MODEL_AUTO_UPDATE", "").lower() == "true"
)


AUDIO_STT_OPENAI_API_BASE_URL = PersistentConfig(
    "AUDIO_STT_OPENAI_API_BASE_URL",
    "audio.stt.openai.api_base_url",
    os.getenv("AUDIO_STT_OPENAI_API_BASE_URL", OPENAI_API_BASE_URL),
)

AUDIO_STT_OPENAI_API_KEY = PersistentConfig(
    "AUDIO_STT_OPENAI_API_KEY",
    "audio.stt.openai.api_key",
    os.getenv("AUDIO_STT_OPENAI_API_KEY", OPENAI_API_KEY),
)

AUDIO_STT_ENGINE = PersistentConfig(
    "AUDIO_STT_ENGINE",
    "audio.stt.engine",
    os.getenv("AUDIO_STT_ENGINE", ""),
)

AUDIO_STT_MODEL = PersistentConfig(
    "AUDIO_STT_MODEL",
    "audio.stt.model",
    os.getenv("AUDIO_STT_MODEL", ""),
)

AUDIO_TTS_OPENAI_API_BASE_URL = PersistentConfig(
    "AUDIO_TTS_OPENAI_API_BASE_URL",
    "audio.tts.openai.api_base_url",
    os.getenv("AUDIO_TTS_OPENAI_API_BASE_URL", OPENAI_API_BASE_URL),
)
AUDIO_TTS_OPENAI_API_KEY = PersistentConfig(
    "AUDIO_TTS_OPENAI_API_KEY",
    "audio.tts.openai.api_key",
    os.getenv("AUDIO_TTS_OPENAI_API_KEY", OPENAI_API_KEY),
)

AUDIO_TTS_API_KEY = PersistentConfig(
    "AUDIO_TTS_API_KEY",
    "audio.tts.api_key",
    os.getenv("AUDIO_TTS_API_KEY", ""),
)

AUDIO_TTS_ENGINE = PersistentConfig(
    "AUDIO_TTS_ENGINE",
    "audio.tts.engine",
    os.getenv("AUDIO_TTS_ENGINE", ""),
)


AUDIO_TTS_MODEL = PersistentConfig(
    "AUDIO_TTS_MODEL",
    "audio.tts.model",
    os.getenv("AUDIO_TTS_MODEL", "tts-1"),  # OpenAI default model
)

AUDIO_TTS_VOICE = PersistentConfig(
    "AUDIO_TTS_VOICE",
    "audio.tts.voice",
    os.getenv("AUDIO_TTS_VOICE", "alloy"),  # OpenAI default voice
)

AUDIO_TTS_SPLIT_ON = PersistentConfig(
    "AUDIO_TTS_SPLIT_ON",
    "audio.tts.split_on",
    os.getenv("AUDIO_TTS_SPLIT_ON", "punctuation"),
)

AUDIO_TTS_AZURE_SPEECH_REGION = PersistentConfig(
    "AUDIO_TTS_AZURE_SPEECH_REGION",
    "audio.tts.azure.speech_region",
    os.getenv("AUDIO_TTS_AZURE_SPEECH_REGION", "eastus"),
)

AUDIO_TTS_AZURE_SPEECH_OUTPUT_FORMAT = PersistentConfig(
    "AUDIO_TTS_AZURE_SPEECH_OUTPUT_FORMAT",
    "audio.tts.azure.speech_output_format",
    os.getenv(
        "AUDIO_TTS_AZURE_SPEECH_OUTPUT_FORMAT", "audio-24khz-160kbitrate-mono-mp3"
    ),
)

ENABLE_LDAP = PersistentConfig(
    "ENABLE_LDAP",
    "ldap.enable",
    os.environ.get("ENABLE_LDAP", "false").lower() == "true",
)

LDAP_SERVER_LABEL = PersistentConfig(
    "LDAP_SERVER_LABEL",
    "ldap.server.label",
    os.environ.get("LDAP_SERVER_LABEL", "LDAP Server"),
)

LDAP_SERVER_HOST = PersistentConfig(
    "LDAP_SERVER_HOST",
    "ldap.server.host",
    os.environ.get("LDAP_SERVER_HOST", "localhost"),
)

LDAP_SERVER_PORT = PersistentConfig(
    "LDAP_SERVER_PORT",
    "ldap.server.port",
    int(os.environ.get("LDAP_SERVER_PORT", "389")),
)

LDAP_ATTRIBUTE_FOR_USERNAME = PersistentConfig(
    "LDAP_ATTRIBUTE_FOR_USERNAME",
    "ldap.server.attribute_for_username",
    os.environ.get("LDAP_ATTRIBUTE_FOR_USERNAME", "uid"),
)

LDAP_APP_DN = PersistentConfig(
    "LDAP_APP_DN", "ldap.server.app_dn", os.environ.get("LDAP_APP_DN", "")
)

LDAP_APP_PASSWORD = PersistentConfig(
    "LDAP_APP_PASSWORD",
    "ldap.server.app_password",
    os.environ.get("LDAP_APP_PASSWORD", ""),
)

LDAP_SEARCH_BASE = PersistentConfig(
    "LDAP_SEARCH_BASE", "ldap.server.users_dn", os.environ.get("LDAP_SEARCH_BASE", "")
)

LDAP_SEARCH_FILTERS = PersistentConfig(
    "LDAP_SEARCH_FILTER",
    "ldap.server.search_filter",
    os.environ.get("LDAP_SEARCH_FILTER", ""),
)

LDAP_USE_TLS = PersistentConfig(
    "LDAP_USE_TLS",
    "ldap.server.use_tls",
    os.environ.get("LDAP_USE_TLS", "True").lower() == "true",
)

LDAP_CA_CERT_FILE = PersistentConfig(
    "LDAP_CA_CERT_FILE",
    "ldap.server.ca_cert_file",
    os.environ.get("LDAP_CA_CERT_FILE", ""),
)

LDAP_CIPHERS = PersistentConfig(
    "LDAP_CIPHERS", "ldap.server.ciphers", os.environ.get("LDAP_CIPHERS", "ALL")
)
