"""Environment variables and settings for Open WebUI."""

import os
import pkgutil
import shutil
from pathlib import Path
from typing import Annotated, Literal

import markdown
from bs4 import BeautifulSoup
from loguru import logger
from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode

OPENAI_BASE_URL = "https://api.openai.com/v1"


class Environments(BaseSettings, case_sensitive=True):
    """Environment variables."""

    OPENAI_API_KEY: str = ""
    OPENAI_API_KEYS: Annotated[list[str], NoDecode] = Field(default_factory=list)
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

    @field_validator("OPENAI_API_KEYS")
    @classmethod
    def validate_openai_api_keys(cls, value: str | list[str]) -> list[str]:
        """Validate OpenAI API keys."""
        if isinstance(value, str):
            return [key.strip() for key in value.split(";") if key.strip()]
        return value

    def model_post_init(self, __context):
        """Post init."""
        if len(self.OPENAI_API_KEYS) == 0 and self.OPENAI_API_KEY:
            self.OPENAI_API_KEYS = [self.OPENAI_API_KEY]


env = Environments()

OPEN_WEBUI_DIR = Path(__file__).parent  # the path containing this file
BACKEND_DIR = OPEN_WEBUI_DIR.parent  # the path containing this file


DOCKER = os.environ.get("DOCKER", "False").lower() == "true"


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


WEBUI_NAME = os.environ.get("WEBUI_NAME", "Open WebUI")
if WEBUI_NAME != "Open WebUI":
    WEBUI_NAME += " (Open WebUI)"

WEBUI_FAVICON_URL = "https://openwebui.com/favicon.png"

WEBUI_ENV = os.environ.get("ENV", "dev")

FROM_INIT_PY = os.environ.get("FROM_INIT_PY", "False").lower() == "true"

VERSION = "0.5.4"


def parse_section(section):
    """Parse each section of the changelog."""
    items = []
    for li in section.find_all("li"):
        # Extract raw HTML string
        raw_html = str(li)

        # Extract text without HTML tags
        text = li.get_text(separator=" ", strip=True)

        # Split into title and content
        parts = text.split(": ", 1)
        title = parts[0].strip() if len(parts) > 1 else ""
        content = parts[1].strip() if len(parts) > 1 else text

        items.append({"title": title, "content": content, "raw": raw_html})
    return items


changelog_content = (pkgutil.get_data("open_webui", "CHANGELOG.md") or b"").decode()


# Convert markdown content to HTML
html_content = markdown.markdown(changelog_content)

# Parse the HTML content
soup = BeautifulSoup(html_content, "html.parser")

# Initialize JSON structure
changelog_json = {}

# Iterate over each version
for version in soup.find_all("h2"):
    version_number = version.get_text().strip().split(" - ")[0][1:-1]  # Remove brackets
    date = version.get_text().strip().split(" - ")[1]

    version_data = {"date": date}

    # Find the next sibling that is a h3 tag (section title)
    current = version.find_next_sibling()

    while current and current.name != "h2":
        if current.name == "h3":
            section_title = current.get_text().lower()  # e.g., "added", "fixed"
            section_items = parse_section(current.find_next_sibling("ul"))
            version_data[section_title] = section_items

        # Move to the next element
        current = current.find_next_sibling()

    changelog_json[version_number] = version_data


CHANGELOG = changelog_json

SAFE_MODE = os.environ.get("SAFE_MODE", "false").lower() == "true"

ENABLE_FORWARD_USER_INFO_HEADERS = (
    os.environ.get("ENABLE_FORWARD_USER_INFO_HEADERS", "False").lower() == "true"
)

WEBUI_BUILD_HASH = os.environ.get("WEBUI_BUILD_HASH", "dev-build")

DATA_DIR = Path(os.getenv("DATA_DIR", BACKEND_DIR / "data")).resolve()

if FROM_INIT_PY:
    NEW_DATA_DIR = Path(os.getenv("DATA_DIR", OPEN_WEBUI_DIR / "data")).resolve()
    NEW_DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Check if the data directory exists in the package directory
    if DATA_DIR.exists() and DATA_DIR != NEW_DATA_DIR:
        logger.info(f"Moving {DATA_DIR} to {NEW_DATA_DIR}")
        for item in DATA_DIR.iterdir():
            dest = NEW_DATA_DIR / item.name
            if item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest)

        # Zip the data directory
        shutil.make_archive(str(DATA_DIR.parent / "open_webui_data"), "zip", DATA_DIR)

        # Remove the old data directory
        shutil.rmtree(DATA_DIR)

    DATA_DIR = Path(os.getenv("DATA_DIR", OPEN_WEBUI_DIR / "data"))


STATIC_DIR = Path(os.getenv("STATIC_DIR", OPEN_WEBUI_DIR / "static"))

FONTS_DIR = Path(os.getenv("FONTS_DIR", OPEN_WEBUI_DIR / "static" / "fonts"))

FRONTEND_BUILD_DIR = Path(
    os.getenv("FRONTEND_BUILD_DIR", BACKEND_DIR / "build")
).resolve()

if FROM_INIT_PY:
    FRONTEND_BUILD_DIR = Path(
        os.getenv("FRONTEND_BUILD_DIR", OPEN_WEBUI_DIR / "frontend")
    ).resolve()


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
    os.environ.get("ENABLE_REALTIME_CHAT_SAVE", "False").lower() == "true"
)

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

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
