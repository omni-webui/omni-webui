import importlib.util
import re
import warnings
from datetime import timedelta
from functools import cached_property, lru_cache
from itertools import zip_longest
from pathlib import Path
from secrets import token_urlsafe
from typing import (
    Annotated,
    Any,
    Literal,
    NotRequired,
    Self,
    Sequence,
    TypedDict,
    cast,
    get_args,
    get_type_hints,
)

from mcp import StdioServerParameters
from ollama import AsyncClient
from openai import AsyncOpenAI
from openai.types.audio import SpeechCreateParams, SpeechModel
from platformdirs import PlatformDirs
from pydantic import (
    AliasChoices,
    Field,
    ValidationError,
    ValidatorFunctionWrapHandler,
    WrapValidator,
    field_serializer,
    field_validator,
    model_validator,
)
from pydantic_settings import (
    BaseSettings as _BaseSettings,
)
from pydantic_settings import (
    JsonConfigSettingsSource,
    NoDecode,
    PydanticBaseSettingsSource,
    SecretsSettingsSource,
)
from typing_extensions import deprecated

from ._compat import find_case_path, save_secret_key
from ._logger import logger
from ._types import MutableBaseModel as BaseModel


class BaseSettings(BaseModel, _BaseSettings): ...


class Audio(BaseModel):
    class TTS(BaseSettings, env_prefix="AUDIO_TTS_"):
        class Azure(BaseSettings, env_prefix="AUDIO_TTS_AZURE_"):
            speech_region: str = "eastus"  # East US
            speech_output_format: str = "audio-24khz-160kbitrate-mono-mp3"

        azure: Azure = Field(default_factory=Azure)
        engine: str = ""
        model: str = get_args(SpeechModel)[0]
        voice: str = get_args(get_type_hints(SpeechCreateParams)["voice"])[0]
        split_on: str = "punctuation"

    tts: TTS = Field(default_factory=TTS)

    class STT(BaseSettings, env_prefix="AUDIO_STT_"):
        engine: str = ""

    stt: STT = Field(default_factory=STT)


@deprecated("Open WebUI self-defined rules, would be remove @1.0")
def parse_duration(duration: str) -> timedelta | None:
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
    if duration is None:
        return "-1"
    return f"{duration.total_seconds()}s"


@deprecated("Backward-compatible with Open WebUI, would be removed @1.0")
def validate_duration(value: Any, handler: ValidatorFunctionWrapHandler):
    try:
        return handler(value)
    except ValidationError:
        try:
            return parse_duration(value)
        except ValueError:
            raise ValidationError


class Auth(BaseSettings):
    class APIKey(BaseSettings):
        enable: Annotated[
            bool, Field(validation_alias=AliasChoices("ENABLE_API_KEY", "enable"))
        ] = True

    api_key: APIKey = Field(default_factory=APIKey)
    jwt_expiry: Annotated[
        timedelta | None,
        Field(validation_alias=AliasChoices("JWT_EXPIRES_IN", "jwt_expiry")),
        WrapValidator(validate_duration),
    ] = None


class ArenaModel(BaseModel):
    class Meta(BaseModel):
        profile_image_url: str = "/favicon.png"
        description: str = "Submit your questions to anonymous AI chatbots and vote on the best response."

    id: str = "arena-model"
    name: str = "Arena Model"
    meta: Meta = Field(default_factory=Meta)


class Evaluation(BaseModel):
    class Arena(BaseSettings):
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


class ImageGeneration(BaseSettings):
    enable: Annotated[
        bool, Field(validation_alias=AliasChoices("ENABLE_IMAGE_GENERATION", "enable"))
    ] = True


class LDAP(BaseModel):
    enable: Annotated[
        bool, Field(validation_alias=AliasChoices("ENABLE_LDAP", "enable"))
    ] = False


class OAuthProvider(TypedDict):
    client_id: str
    client_secret: str
    scope: str
    redirect_uri: str
    name: NotRequired[str]


class OAuth(BaseModel):
    class Provider(BaseSettings):
        client_id: str = ""
        client_secret: str = ""
        scope: str = "openid email profile"
        redirect_uri: str = ""

    class Google(Provider, env_prefix="GOOGLE_"): ...

    class Microsoft(Provider, env_prefix="MICROSOFT_"):
        tenant_id: str = ""

    class OIDC(Provider, env_prefix="OAUTH_"):
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
        enable_role_mapping: Annotated[
            bool,
            Field(
                validation_alias=AliasChoices(
                    "ENABLE_OAUTH_ROLE_MANAGEMENT", "enable_role_mapping"
                )
            ),
        ] = False
        roles_claim: str = "roles"
        allowed_roles: list[str] = ["user", "admin"]
        admin_roles: list[str] = ["admin"]

    enable_signup: Annotated[
        bool,
        Field(validation_alias=AliasChoices("ENABLE_OAUTH_SIGNUP", "enable_signup")),
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

    @property
    def providers(self) -> dict[str, OAuthProvider]:
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
    enable: bool = True
    prefix_id: str | None = None


class Ollama(BaseSettings, env_prefix="OLLAMA_"):
    enable: Annotated[
        bool, Field(validation_alias=AliasChoices("ENABLE_OLLAMA_API", "enable"))
    ] = True
    base_urls: Annotated[list[str], NoDecode] = Field(default_factory=list)
    api_configs: dict[str, ClientConfig] = Field(default_factory=dict)

    @field_validator("base_urls", mode="before")
    @classmethod
    def decode_numbers(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return v.split(";")
        if isinstance(v, list) and all(isinstance(i, str) for i in v):
            return v
        raise ValidationError("Invalid value")

    def model_post_init(self, __context):
        self.base_urls = [base_url for base_url in self.base_urls if base_url]
        if not self.base_urls:
            self.base_urls = ["http://127.0.0.1:11434"]

    @cached_property
    def clients(self) -> list[AsyncClient]:
        return [AsyncClient(host=base_url) for base_url in self.base_urls]


OPENAI_BASE_URL = "https://api.openai.com/v1"


class OpenAI(BaseSettings, env_prefix="OPENAI_"):
    enable: Annotated[
        bool, Field(validation_alias=AliasChoices("ENABLE_OPENAI_API", "enable"))
    ] = True
    api_keys: Annotated[list[str], NoDecode] = Field(default_factory=list)
    api_base_urls: Annotated[list[str], NoDecode] = Field(default_factory=list)
    api_configs: dict[str, ClientConfig] = Field(default_factory=dict)

    @field_validator("api_keys", "api_base_urls", mode="before")
    @classmethod
    def decode_numbers(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return v.split(";")
        if isinstance(v, list) and all(isinstance(i, str) for i in v):
            return v
        raise ValidationError("Invalid value")

    @cached_property
    def clients(self) -> list[AsyncOpenAI]:
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


class RAG(BaseModel):
    class Web(BaseModel):
        class Search(BaseSettings):
            enable: Annotated[
                bool,
                Field(validation_alias=AliasChoices("ENABLE_RAG_WEB_SEARCH", "enable")),
            ] = True

        search: Search = Field(default_factory=Search)

    web: Web = Field(default_factory=Web)

    class File(BaseSettings, env_prefix="RAG_FILE_"):
        max_count: int | None = None
        max_size: float | None = None
        """Max file size in MB"""

    file: File = Field(default_factory=File)


class UI(BaseSettings):
    class PromptSuggestion(BaseModel):
        title: tuple[str, str]
        content: str

    default_locale: str = ""
    prompt_suggestions: list[PromptSuggestion] = Field(default_factory=list)
    enable_signup: bool = True
    default_models: str | None = None
    ENABLE_LOGIN_FORM: bool = True
    enable_community_sharing: bool = True
    enable_message_rating: bool = True


class User(BaseModel):
    class Permissions(BaseModel):
        class Workspace(BaseSettings):
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
            file_upload: bool = True
            delete: bool = True
            edit: bool = True
            temporary: bool = True

        chat: Chat = Field(default_factory=Chat)

    permissions: Permissions = Field(default_factory=Permissions)


@deprecated("Backward compatibility with Open WebUI, will be removed >= 1.0")
class Config(BaseModel, nested_model_default_partial_update=True):
    version: int = 0
    audio: Audio = Field(default_factory=Audio)
    auth: Auth = Field(default_factory=Auth)
    evaluation: Evaluation = Field(default_factory=Evaluation)
    image_generation: ImageGeneration = Field(default_factory=ImageGeneration)
    ldap: LDAP = Field(default_factory=LDAP)
    oauth: OAuth = Field(default_factory=OAuth)
    ollama: Ollama = Field(default_factory=Ollama)
    openai: OpenAI = Field(default_factory=OpenAI)
    rag: RAG = Field(default_factory=RAG)
    ui: UI = Field(default_factory=UI)
    user: User = Field(default_factory=User)


@lru_cache
def get_package_dir(name: str) -> Path:
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
    """Settings from environment variables (and dotenv files), backward compatible with Open WebUI"""

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
        if not self.data_dir.exists():
            self.data_dir.mkdir(parents=True)
        if not self.database_url:
            self.database_url = f"sqlite:///{self.data_dir / 'webui.db'}"
        return self

    @model_validator(mode="after")
    def save_secret_key(self):
        secrets_dir = cast(Path, self.model_config.get("secrets_dir"))
        if not (key_file := secrets_dir / ".webui_secret_key").exists():
            logger.info(f"Generating a new secret key and saving it to {key_file}")
            key_file.write_text(self.webui_secret_key)
        return self

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[_BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
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
        save_secret_key(self.secret_key, Path.cwd() / ".env")

    @field_serializer("frontend_dir")
    @classmethod
    def serialize_path(cls, path: Path) -> str:
        return str(path.resolve())

    def __hash__(self):
        return hash(self.model_dump_json())

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[_BaseSettings],
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
            JsonConfigSettingsSource(settings_cls),
        )

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
