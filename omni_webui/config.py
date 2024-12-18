import importlib.util
from functools import lru_cache
from pathlib import Path
from secrets import token_urlsafe
from typing import Annotated, NotRequired, Self, TypedDict, cast

from pydantic import Field, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SecretsSettingsSource,
    SettingsConfigDict,
)

from ._compat import find_case_path
from ._logger import logger
from ._types import MutableBaseModel


class Audio(MutableBaseModel):
    class TTS(MutableBaseModel, BaseSettings):
        model_config = SettingsConfigDict(env_prefix="AUDIO_TTS_")

        class Azure(MutableBaseModel, BaseSettings):
            model_config = SettingsConfigDict(env_prefix="AUDIO_TTS_AZURE_")
            speech_region: str = "eastus"  # East US
            speech_output_format: str = "audio-24khz-160kbitrate-mono-mp3"

        azure: Azure = Field(default_factory=Azure)
        engine: str = ""
        model: str = "tts-1"  # OpenAI default model
        voice: str = "alloy"  # OpenAI default voice
        split_on: str = "punctuation"

    tts: TTS = Field(default_factory=TTS)

    class STT(MutableBaseModel, BaseSettings):
        model_config = SettingsConfigDict(env_prefix="AUDIO_STT")
        engine: str = ""

    stt: STT = Field(default_factory=STT)


class Auth(MutableBaseModel, BaseSettings):
    class APIKey(MutableBaseModel, BaseSettings):
        enable: Annotated[bool, Field(alias="ENABLE_API_KEY")] = True

    api_key: APIKey = Field(default_factory=APIKey)


class ImageGeneration(MutableBaseModel, BaseSettings):
    enable: Annotated[bool, Field(alias="ENABLE_IMAGE_GENERATION")] = True


class LDAP(MutableBaseModel):
    enable: Annotated[bool, Field(alias="ENABLE_LDAP")] = False


class OAuthProvider(TypedDict):
    client_id: str
    client_secret: str
    scope: str
    redirect_uri: str
    name: NotRequired[str]


class OAuth(MutableBaseModel):
    class Provider(MutableBaseModel, BaseSettings):
        client_id: str = ""
        client_secret: str = ""
        scope: str = "openid email profile"
        redirect_uri: str = ""

    class Google(Provider):
        model_config = SettingsConfigDict(env_prefix="GOOGLE_")

    class Microsoft(Provider):
        model_config = SettingsConfigDict(env_prefix="MICROSOFT_")
        tenant_id: str = ""

    class OIDC(Provider):
        model_config = SettingsConfigDict(env_prefix="OAUTH_")
        provider_url: Annotated[
            str, Field(serialization_alias="server_metadata_url")
        ] = ""
        provider_name: str = "SSO"
        username_claim: str = "name"
        avatar_claim: Annotated[str, Field(alias="OAUTH_PICTURE_CLAIM")] = "picture"
        email_claim: str = "email"
        enable_role_mapping: Annotated[
            bool, Field(alias="ENABLE_OAUTH_ROLE_MANAGEMENT")
        ] = False
        roles_claim: str = "roles"
        allowed_roles: list[str] = ["user", "admin"]
        admin_roles: list[str] = ["admin"]

    enable_signup: Annotated[bool, Field(alias="ENABLE_OAUTH_SIGNUP")] = False
    merge_accounts_by_email: Annotated[
        bool, Field(alias="OAUTH_MERGE_ACCOUNTS_BY_EMAIL")
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


class RAG(MutableBaseModel):
    class Web(MutableBaseModel):
        class Search(MutableBaseModel, BaseSettings):
            enable: Annotated[bool, Field(alias="ENABLE_RAG_WEB_SEARCH")] = True

        search: Search = Field(default_factory=Search)

    web: Web = Field(default_factory=Web)

    class File(MutableBaseModel, BaseSettings):
        max_count: Annotated[int | None, Field(alias="RAG_FILE_MAX_COUNT")] = None
        max_size: Annotated[float | None, Field(alias="RAG_FILE_MAX_SIZE")] = None
        """Max file size in MB"""

    file: File = Field(default_factory=File)


class UI(MutableBaseModel, BaseSettings):
    class PromptSuggestion(MutableBaseModel):
        title: tuple[str, str]
        content: str

    default_locale: str = ""
    prompt_suggestions: list[PromptSuggestion] = Field(default_factory=list)
    enable_signup: bool = True
    default_models: str | None = None
    ENABLE_LOGIN_FORM: bool = True
    enable_community_sharing: bool = True
    enable_message_rating: bool = True


class User(MutableBaseModel):
    class Permissions(MutableBaseModel):
        class Workspace(MutableBaseModel, BaseSettings):
            models: Annotated[
                bool, Field(alias="USER_PERMISSIONS_WORKSPACE_MODELS_ACCESS")
            ] = True
            knowledge: Annotated[
                bool, Field(alias="USER_PERMISSIONS_WORKSPACE_KNOWLEDGE_ACCESS")
            ] = True
            prompts: Annotated[
                bool, Field(alias="USER_PERMISSIONS_WORKSPACE_PROMPTS_ACCESS")
            ] = True
            tools: Annotated[
                bool, Field(alias="USER_PERMISSIONS_WORKSPACE_TOOLS_ACCESS")
            ] = True

        workspace: Workspace = Field(default_factory=Workspace)

        class Chat(MutableBaseModel, BaseSettings):
            model_config = SettingsConfigDict(env_prefix="USER_PERMISSIONS_CHAT_")
            file_upload: bool = True
            delete: bool = True
            edit: bool = True
            temporary: bool = True

        chat: Chat = Field(default_factory=Chat)

    permissions: Permissions = Field(default_factory=Permissions)


class Config(MutableBaseModel, extra="allow"):
    version: int = 0
    audio: Audio = Field(default_factory=Audio)
    auth: Auth = Field(default_factory=Auth)
    image_generation: ImageGeneration = Field(default_factory=ImageGeneration)
    ldap: LDAP = Field(default_factory=LDAP)
    oauth: OAuth = Field(default_factory=OAuth)
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


class Environments(BaseSettings):
    """Settings from environment variables (and dotenv files), backward compatible with Open WebUI"""

    model_config = SettingsConfigDict(secrets_dir=Path.cwd())

    data_dir: Path = get_package_dir("open_webui") / "data"
    frontend_build_dir: Path = get_package_dir("omni_webui") / "frontend"
    database_url: str = ""
    enable_admin_export: bool = True
    enable_admin_chat_access: bool = True
    webui_name: str = "Omni WebUI"
    webui_secret_key: str = Field(default_factory=lambda: token_urlsafe(12))
    webui_auth: bool = True

    @model_validator(mode="after")
    def setup_default_values(self) -> Self:
        if not self.data_dir.exists():
            self.data_dir.mkdir(parents=True)
        if not self.database_url:
            self.database_url = f"sqlite+aiosqlite:///{self.data_dir / 'webui.db'}"
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

    def __hash__(self):
        return hash(self.model_dump_json())
