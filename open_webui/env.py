"""Environment variables and settings for Open WebUI."""

import importlib.util
import os
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlparse

import valkey.asyncio
from fastapi import Depends
from loguru import logger
from platformdirs import PlatformDirs
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings

OPENAI_BASE_URL = "https://api.openai.com/v1"
OLLAMA_HOST = "http://127.0.0.1:11434"


D = PlatformDirs(appname="omni-webui")


@lru_cache
def get_package_dir(name: str) -> Path:
    """Get the directory of a package."""
    spec = importlib.util.find_spec(name)
    if spec is None:
        raise ImportError(f"{name} module not found")
    if spec.submodule_search_locations is None:
        raise ValueError(f"{name} module not installed correctly")
    return Path(spec.submodule_search_locations[0])


class Environments(BaseSettings, case_sensitive=True):
    """Environment variables."""

    DATA_DIR: str = D.user_data_dir
    UPLOAD_DIR: str = ""
    STATIC_DIR: Path = get_package_dir("open_webui") / "static"
    FONTS_DIR: Path = get_package_dir("open_webui") / "static" / "fonts"
    DATABASE_URL: str = ""
    DATABASE_POOL_SIZE: int = 0
    DATABASE_POOL_TIMEOUT: int = 30
    DATABASE_POOL_RECYCLE: int = 3600
    DATABASE_POOL_MAX_OVERFLOW: int = 0
    PGVECTOR_DB_URL: str = ""
    DOCKER: bool = False
    FRONTEND_BUILD_DIR: Path = get_package_dir("open_webui") / "frontend"
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: Annotated[
        str,
        Field(validation_alias=AliasChoices("OPENAI_BASE_URL", "OPENAI_API_BASE_URL")),
    ] = OPENAI_BASE_URL
    USE_CUDA_DOCKER: bool = False
    WEBUI_AUTH: bool = True
    WEBUI_SECRET_KEY: Annotated[
        str,
        Field(
            validation_alias=AliasChoices("WEBUI_SECRET_KEY", "WEBUI_JWT_SECRET_KEY")
        ),
    ] = "t0p-s3cr3t"
    WEBUI_SESSION_COOKIE_SAME_SITE: Literal["lax", "strict", "none"] = "lax"
    WEBUI_SESSION_COOKIE_SECURE: bool = False
    WEBUI_ENV: Literal["dev", "prod"] = "dev"
    WEBUI_NAME: str = "Omni WebUI"
    REDIS_URL: Annotated[
        str, Field(validation_alias=AliasChoices("WEBSOCKET_REDIS_URL", "REDIS_URL"))
    ] = "redis://localhost:6379/0"
    RAG_EMBEDDING_MODEL_TRUST_REMOTE_CODE: bool = True
    RAG_RERANKING_MODEL_TRUST_REMOTE_CODE: bool = True
    RAG_EMBEDDING_MODEL_AUTO_UPDATE: bool = True
    RAG_RERANKING_MODEL_AUTO_UPDATE: bool = True
    OFFLINE_MODE: bool = False
    PGVECTOR_INITIALIZE_MAX_VECTOR_LENGTH: int = 1536

    def model_post_init(self, __context):
        """Post init."""
        if self.DATABASE_URL == "":
            self.data_path.mkdir(parents=True, exist_ok=True)
            self.DATABASE_URL = f"sqlite:///{self.data_path / 'webui.db'}"
        if self.PGVECTOR_DB_URL == "" and self.DATABASE_URL.startswith("postgresql"):
            self.PGVECTOR_DB_URL = self.DATABASE_URL
        if self.UPLOAD_DIR == "":
            self.UPLOAD_DIR = f"{self.DATA_DIR}/uploads"

    @property
    def data_path(self) -> Path:
        """Get the data path."""
        return Path(self.DATA_DIR) if "://" not in self.DATA_DIR else D.user_data_path

    def __hash__(self):
        return hash(self.model_dump_json())


env = Environments()
EnvDep = Annotated[Environments, Depends(lambda: env)]

OPEN_WEBUI_DIR = Path(__file__).parent  # the path containing this file


def get_device_type() -> Literal["cpu", "cuda", "mps"]:
    """Get device type embedding models.

    "cpu" (default), "cuda" (nvidia gpu required) or "mps" (apple silicon) - choosing
    this right can lead to better performance

    Returns
    -------
    Literal["cpu", "cuda", "mps"]
        device type

    """
    try:
        import torch
    except ImportError:
        return "cpu"
    if torch.cuda.is_available() and env.USE_CUDA_DOCKER:
        return "cuda"
    if torch.backends.mps.is_available() and torch.backends.mps.is_built():
        return "mps"
    return "cpu"


DEVICE_TYPE = get_device_type()

log_levels = ["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]

GLOBAL_LOG_LEVEL = os.environ.get("GLOBAL_LOG_LEVEL", "").upper()
if GLOBAL_LOG_LEVEL not in log_levels:
    GLOBAL_LOG_LEVEL = "INFO"

log_sources = [
    "AUDIO",
    "COMFYUI",
    "CONFIG",
    "DB",
    "IMAGES",
    "MAIN",
    "MODELS",
    "OLLAMA",
    "OPENAI",
    "RAG",
    "WEBHOOK",
    "SOCKET",
]

SRC_LOG_LEVELS = {}

for source in log_sources:
    log_env_var = source + "_LOG_LEVEL"
    SRC_LOG_LEVELS[source] = os.environ.get(log_env_var, "").upper()
    if SRC_LOG_LEVELS[source] not in log_levels:
        SRC_LOG_LEVELS[source] = GLOBAL_LOG_LEVEL
    logger.info(f"{log_env_var}: {SRC_LOG_LEVELS[source]}")


WEBUI_FAVICON_URL = "https://openwebui.com/favicon.png"

VERSION = "0.5.4"

ENABLE_FORWARD_USER_INFO_HEADERS = (
    os.environ.get("ENABLE_FORWARD_USER_INFO_HEADERS", "False").lower() == "true"
)

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

RESET_CONFIG_ON_START = (
    os.environ.get("RESET_CONFIG_ON_START", "False").lower() == "true"
)

ENABLE_REALTIME_CHAT_SAVE = (
    os.environ.get("ENABLE_REALTIME_CHAT_SAVE", "False").lower() == "true"
)

WEBUI_AUTH_TRUSTED_EMAIL_HEADER = os.environ.get(
    "WEBUI_AUTH_TRUSTED_EMAIL_HEADER", None
)
WEBUI_AUTH_TRUSTED_NAME_HEADER = os.environ.get("WEBUI_AUTH_TRUSTED_NAME_HEADER", None)

BYPASS_MODEL_ACCESS_CONTROL = (
    os.environ.get("BYPASS_MODEL_ACCESS_CONTROL", "False").lower() == "true"
)

if env.WEBUI_AUTH and not env.WEBUI_SECRET_KEY:
    raise ValueError("Required environment variable not found. Terminating now.")

ENABLE_WEBSOCKET_SUPPORT = (
    os.environ.get("ENABLE_WEBSOCKET_SUPPORT", "True").lower() == "true"
)

WEBSOCKET_MANAGER = os.environ.get("WEBSOCKET_MANAGER", "")

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

if env.OFFLINE_MODE:
    os.environ["HF_HUB_OFFLINE"] = "1"


def get_valkey() -> valkey.asyncio.Valkey:
    """Get valkey."""
    result = urlparse(env.REDIS_URL)
    return valkey.asyncio.Valkey(
        host=result.hostname or "localhost",
        port=result.port or 6379,
        db=0,
    )


ValkeyDep = Annotated[valkey.asyncio.Valkey, Depends(get_valkey)]
