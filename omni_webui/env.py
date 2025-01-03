import os
from pathlib import Path
from secrets import token_urlsafe
from typing import Annotated, Literal

from fastapi import Depends
from loguru import logger
from pydantic import Field
from pydantic_settings import BaseSettings
from typing_extensions import deprecated

from omni_webui import D, get_package_dir
from omni_webui._exc import EnvironmentVariableNotFound
from omni_webui.settings import Settings

settings = Settings()

OPEN_WEBUI_DIR = Path(__file__).parent  # the path containing this file
BACKEND_DIR = OPEN_WEBUI_DIR.parent  # the path containing this file

DOCKER = os.environ.get("DOCKER", "False").lower() == "true"

if os.environ.get("USE_CUDA_DOCKER", "false").lower() == "true":
    try:
        import torch

        assert torch.cuda.is_available(), "CUDA not available"
        DEVICE_TYPE = "cuda"
    except Exception as e:
        cuda_error = (
            "Error when testing CUDA but USE_CUDA_DOCKER is true. "
            f"Resetting USE_CUDA_DOCKER to false: {e}"
        )
        logger.exception(cuda_error)
        os.environ["USE_CUDA_DOCKER"] = "false"
        DEVICE_TYPE = "cpu"
else:
    DEVICE_TYPE = "cpu"


WEBUI_NAME = os.environ.get("WEBUI_NAME", "Open WebUI")
if WEBUI_NAME != "Open WebUI":
    WEBUI_NAME += " (Open WebUI)"

WEBUI_FAVICON_URL = "https://openwebui.com/favicon.png"

ENV = os.environ.get("ENV", "dev")

ENABLE_FORWARD_USER_INFO_HEADERS = (
    os.environ.get("ENABLE_FORWARD_USER_INFO_HEADERS", "False").lower() == "true"
)

WEBUI_BUILD_HASH = os.environ.get("WEBUI_BUILD_HASH", "dev-build")

DATA_DIR = Path(settings.data_dir)

STATIC_DIR = Path(os.getenv("STATIC_DIR", OPEN_WEBUI_DIR / "static"))

FONTS_DIR = Path(os.getenv("FONTS_DIR", OPEN_WEBUI_DIR / "static" / "fonts"))

FRONTEND_BUILD_DIR = settings.frontend_dir


####################################
# Database
####################################

# Check if the file exists
if os.path.exists(f"{DATA_DIR}/ollama.db"):
    # Rename the file
    os.rename(f"{DATA_DIR}/ollama.db", f"{DATA_DIR}/webui.db")
    logger.info("Database migrated from Ollama-WebUI successfully.")
else:
    pass

DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{DATA_DIR}/webui.db")

# Replace the postgres:// with postgresql://
if "postgres://" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://")

DATABASE_POOL_SIZE = os.environ.get("DATABASE_POOL_SIZE", 0)

if DATABASE_POOL_SIZE == "":
    DATABASE_POOL_SIZE = 0
else:
    try:
        DATABASE_POOL_SIZE = int(DATABASE_POOL_SIZE)
    except Exception:
        DATABASE_POOL_SIZE = 0

DATABASE_POOL_MAX_OVERFLOW = os.environ.get("DATABASE_POOL_MAX_OVERFLOW", 0)

if DATABASE_POOL_MAX_OVERFLOW == "":
    DATABASE_POOL_MAX_OVERFLOW = 0
else:
    try:
        DATABASE_POOL_MAX_OVERFLOW = int(DATABASE_POOL_MAX_OVERFLOW)
    except Exception:
        DATABASE_POOL_MAX_OVERFLOW = 0

DATABASE_POOL_TIMEOUT = os.environ.get("DATABASE_POOL_TIMEOUT", 30)

if DATABASE_POOL_TIMEOUT == "":
    DATABASE_POOL_TIMEOUT = 30
else:
    try:
        DATABASE_POOL_TIMEOUT = int(DATABASE_POOL_TIMEOUT)
    except Exception:
        DATABASE_POOL_TIMEOUT = 30

DATABASE_POOL_RECYCLE = os.environ.get("DATABASE_POOL_RECYCLE", 3600)

if DATABASE_POOL_RECYCLE == "":
    DATABASE_POOL_RECYCLE = 3600
else:
    try:
        DATABASE_POOL_RECYCLE = int(DATABASE_POOL_RECYCLE)
    except Exception:
        DATABASE_POOL_RECYCLE = 3600

RESET_CONFIG_ON_START = (
    os.environ.get("RESET_CONFIG_ON_START", "False").lower() == "true"
)


ENABLE_REALTIME_CHAT_SAVE = (
    os.environ.get("ENABLE_REALTIME_CHAT_SAVE", "True").lower() == "true"
)

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")


WEBUI_AUTH = os.environ.get("WEBUI_AUTH", "True").lower() == "true"
WEBUI_AUTH_TRUSTED_EMAIL_HEADER = os.environ.get(
    "WEBUI_AUTH_TRUSTED_EMAIL_HEADER", None
)
WEBUI_AUTH_TRUSTED_NAME_HEADER = os.environ.get("WEBUI_AUTH_TRUSTED_NAME_HEADER", None)

WEBUI_SECRET_KEY = settings.secret_key

WEBUI_SESSION_COOKIE_SAME_SITE = os.environ.get(
    "WEBUI_SESSION_COOKIE_SAME_SITE",
    os.environ.get("WEBUI_SESSION_COOKIE_SAME_SITE", "lax"),
)

WEBUI_SESSION_COOKIE_SECURE = os.environ.get(
    "WEBUI_SESSION_COOKIE_SECURE",
    os.environ.get("WEBUI_SESSION_COOKIE_SECURE", "false").lower() == "true",
)

if WEBUI_AUTH and WEBUI_SECRET_KEY == "":
    raise EnvironmentVariableNotFound("")

ENABLE_WEBSOCKET_SUPPORT = (
    os.environ.get("ENABLE_WEBSOCKET_SUPPORT", "True").lower() == "true"
)

WEBSOCKET_MANAGER = os.environ.get("WEBSOCKET_MANAGER", "")

WEBSOCKET_REDIS_URL = os.environ.get("WEBSOCKET_REDIS_URL", REDIS_URL)

AIOHTTP_CLIENT_TIMEOUT = os.environ.get("AIOHTTP_CLIENT_TIMEOUT", "")

if AIOHTTP_CLIENT_TIMEOUT == "":
    AIOHTTP_CLIENT_TIMEOUT = None
else:
    try:
        AIOHTTP_CLIENT_TIMEOUT = int(AIOHTTP_CLIENT_TIMEOUT)
    except Exception:
        AIOHTTP_CLIENT_TIMEOUT = 300

AIOHTTP_CLIENT_TIMEOUT_OPENAI_MODEL_LIST = os.environ.get(
    "AIOHTTP_CLIENT_TIMEOUT_OPENAI_MODEL_LIST", ""
)

if AIOHTTP_CLIENT_TIMEOUT_OPENAI_MODEL_LIST == "":
    AIOHTTP_CLIENT_TIMEOUT_OPENAI_MODEL_LIST = None
else:
    try:
        AIOHTTP_CLIENT_TIMEOUT_OPENAI_MODEL_LIST = int(
            AIOHTTP_CLIENT_TIMEOUT_OPENAI_MODEL_LIST
        )
    except Exception:
        AIOHTTP_CLIENT_TIMEOUT_OPENAI_MODEL_LIST = 5

OFFLINE_MODE = os.environ.get("OFFLINE_MODE", "false").lower() == "true"

if OFFLINE_MODE:
    os.environ["HF_HUB_OFFLINE"] = "1"


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
    bypass_model_access_control: bool = False

    def model_post_init(self, __context):
        if not self.data_dir.exists():
            self.data_dir.mkdir(parents=True)
        if not self.database_url:
            self.database_url = f"sqlite:///{self.data_dir / 'webui.db'}"

    def __hash__(self):
        return hash(self.model_dump_json())


# https://github.com/pydantic/pydantic-settings/issues/183
EnvDepends = Annotated[Environments, Depends(lambda: Environments())]
