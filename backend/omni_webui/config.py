import json
import logging
import os
import re
import shutil
from importlib.metadata import metadata
from pathlib import Path
from typing import Any, Literal, Optional, TypedDict

import chromadb
import keepachangelog
import requests
from chromadb import Settings as ChromaSettings
from loguru import logger
from peewee import SqliteDatabase
from playhouse.db_url import connect
from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    HttpUrl,
    ValidationError,
    computed_field,
    model_validator,
)
from pydantic_settings import BaseSettings

OMNI_WEBUI_DIR = Path(__file__).parent
BASE_DIR = OMNI_WEBUI_DIR.parent.parent  # the path containing the backend/


class Settings(BaseSettings):
    """Settings from environment variables"""

    name: str = Field(default="Omni WebUI", alias="webui_name")
    url: HttpUrl = Field(default=HttpUrl("http://localhost:8000"), alias="webui_url")
    favicon_url: HttpUrl = Field(
        default=HttpUrl("https://omni-webui.com/favicon.png"), alias="webui_favicon_url"
    )
    build_hash: str = Field(default="dev-build", alias="webui_build_hash")
    auth: bool = Field(default=True, alias="webui_auth")
    webui_auth_trusted_email_header: str = ""
    webui_secret_key: str = "t0p-s3cr3t"
    ollama_api_base_url: HttpUrl = HttpUrl("http://localhost:11434/api")

    custom_name: str = ""

    env: Literal["dev", "prod"] = "dev"
    data_dir: Path = OMNI_WEBUI_DIR / "data"
    frontend_build_dir: Path = BASE_DIR / "build"
    static_dir: Path = OMNI_WEBUI_DIR / "static"
    docs_dir: Path = Path("")

    database_url: str = ""

    openai_api_key: str = ""
    openai_api_base_url: HttpUrl = HttpUrl("https://api.openai.com/v1")
    enable_admin_export: bool = True
    enable_rag_local_web_fetch: bool = False

    @model_validator(mode="after")
    def default_settings(self):
        if self.database_url == "":
            self.database_url = f"sqlite:///{self.data_dir / "webui.db"}"
        if self.docs_dir == Path(""):
            self.docs_dir = self.data_dir / "docs"
        if self.auth and self.webui_secret_key == "":
            raise ValidationError("Secret key is required for authentication")
        return self

    @computed_field  # type: ignore[misc]
    @property
    def database(self) -> SqliteDatabase:
        engine = connect(self.database_url)
        engine.connect(reuse_if_open=True)
        return engine


settings = Settings()


class PromptSuggestion(TypedDict):
    title: list[str]
    content: str


class Auth(BaseSettings):
    jwt_expiry: str = "-1"
    admin_email: EmailStr | None = None
    show_admin_details: bool = True


class UserPermission(BaseSettings):
    deletion: bool = True


class UserPermissions(BaseSettings):
    chat: UserPermission = UserPermission()


class UI(BaseSettings):
    default_locale: str = "en-US"
    default_user_role: Literal["pending", "user", "admin"] = "pending"
    default_models: str = "llama3"
    enable_signup: bool = True
    enable_community_sharing: bool = True
    prompt_suggestions: list[PromptSuggestion] = [
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
        {
            "title": ["Grammar check", "rewrite it for better readability "],
            "content": 'Check the following sentence for grammar and clarity: "[sentence]". Rewrite it for better readability while maintaining its original meaning.',
        },
    ]
    user_permissions: UserPermissions = UserPermissions()


class Ollama(BaseSettings, env_prefix="ollama_"):
    enable: bool = Field(default=True, alias="enable_ollama_api")
    base_urls: list[HttpUrl] = [HttpUrl("http://localhost:11434")]


class OpenAI(BaseSettings):
    enable: bool = Field(default=True, alias="enable_openai_api")
    api_keys: list[str] = []
    base_urls: list[HttpUrl] = [HttpUrl("https://api.openai.com/v1")]


class WebSearch(BaseSettings):
    enable: bool = Field(default=False, alias="enable_web_search")
    engine: str = ""
    serpstack_api_key: str = ""
    serpstack_https: bool = True
    serper_api_key: str = ""
    searxng_query_url: HttpUrl = HttpUrl("https://localhost:7700")
    google_pse_api_key: str = ""
    google_pse_engine_id: str = ""
    brave_search_api_key: str = ""
    concurrent_requests: int = 10
    result_count: int = 3


class RAG(BaseSettings, env_prefix="rag_"):
    template: str = """Use the following context as your learned knowledge, inside <context></context> XML tags.
<context>
    [context]
</context>

When answer to user:
- If you don't know, just say that you don't know.
- If you don't know when you are not sure, ask for clarification.
Avoid mentioning that you obtained the information from the context.
And answer according to the language of the user's question.

Given the context information, answer the query.
Query: [query]"""
    chunk_size: int = Field(default=1500, alias="chunk_size")
    chunk_overlap: int = Field(default=100, alias="chunk_overlap")
    embedding_engine: str = ""
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    reranking_model: str = ""
    youtube_loader_language: list[str] = ["en"]
    top_k: int = 5
    embedding_openai_batch_size: int = 1
    web_search: WebSearch = WebSearch()
    enable_web_loader_ssl_verification: bool = True
    enable_hybrid_search: bool = False
    pdf_extract_images: bool = False
    relevance_threshold: float = 0.0

    @model_validator(mode="after")
    def default_settings(self):
        if self.reranking_model != "":
            logger.info(f"Reranking model set: {self.reranking_model}")
        return self


class ImageGeneration(BaseSettings):
    enable: bool = Field(default=False, alias="enable_image_generation")
    steps: int = 50
    size: str = "512x512"
    comfyui_base_url: HttpUrl = HttpUrl("http://localhost:8000")
    automatic1111_base_url: HttpUrl = HttpUrl("http://localhost:8000")


class ModelFilter(BaseSettings):
    enabled: bool = Field(default=False, alias="enable_model_filter")
    models: list[str] = []


def config_json_path():
    return settings.data_dir / "config.json"


class Config(BaseSettings, json_file=config_json_path()):
    version: Literal[0] = 0
    ui: UI = UI()
    webhook_url: str = ""
    auth: Auth = Auth()
    ollama: Ollama = Ollama()
    openai: OpenAI = OpenAI()
    rag: RAG = RAG()
    image_generation: ImageGeneration = ImageGeneration()
    model_filter: ModelFilter = ModelFilter()

    def __init__(self):
        super().__init__()

        def get_setattr(cls):
            def __setattr__(this, name: str, value: Any) -> None:
                super(cls, this).__setattr__(name, value)
                self.save()

            return __setattr__

        def get_delattr(cls):
            def __delattr__(this, name: str) -> None:
                super(cls, this).__delattr__(name)
                self.save()

            return __delattr__

        for cls in (Auth, UI, Ollama, RAG, ImageGeneration, OpenAI, ModelFilter):
            cls.__setattr__ = get_setattr(cls)
            cls.__delattr__ = get_delattr(cls)
            name = (
                re.sub(
                    r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", "_", cls.__name__
                ).lower()
                if cls.__name__ != "OpenAI"
                else "openai"
            )
            setattr(self, name, cls())

    def __setattr__(self, name: str, value: Any) -> None:
        super().__setattr__(name, value)
        if not isinstance(getattr(self, name), BaseModel):
            self.save()

    def __delattr__(self, name: str) -> None:
        super().__delattr__(name)
        self.save()

    def save(self):
        with (config_json_path()).open("w") as f:
            f.write(self.model_dump_json(indent=4, exclude_defaults=True))


config = Config()

changelog: str = re.findall(
    r"^# Changelog[\s\S]*",
    metadata("omni_webui")["Description"],
    re.MULTILINE,
)[0]
CHANGELOG = keepachangelog.to_dict(changelog.splitlines(), show_unreleased=True)

####################################
# DATA/FRONTEND BUILD DIR
####################################

DATA_DIR = Path(os.getenv("DATA_DIR", OMNI_WEBUI_DIR / "data")).resolve()

CONFIG_DATA = config.model_dump()

####################################
# Config helpers
####################################


def save_config():
    try:
        with open(f"{DATA_DIR}/config.json", "w") as f:
            json.dump(CONFIG_DATA, f, indent="\t")
    except Exception as e:
        logger.exception(e)


def get_config_value(config_path: str):
    path_parts = config_path.split(".")
    cur_config = CONFIG_DATA
    for key in path_parts:
        if key in cur_config:
            cur_config = cur_config[key]
        else:
            return None
    return cur_config


frontend_favicon = settings.frontend_build_dir / "favicon.png"
if frontend_favicon.exists():
    shutil.copyfile(frontend_favicon, settings.static_dir / "favicon.png")
else:
    logging.warning(f"Frontend favicon not found at {frontend_favicon}")

####################################
# CUSTOM_NAME
####################################
if settings.custom_name:
    try:
        r = requests.get(
            f"https://api.omni-webui.com/api/v1/custom/{settings.custom_name}"
        )
        data = r.json()
        if r.ok:
            if "logo" in data:
                settings.favicon_url = url = (
                    f"https://api.omni-webui.com{data['logo']}"
                    if data["logo"][0] == "/"
                    else data["logo"]
                )

                r = requests.get(url, stream=True)
                if r.status_code == 200:
                    with (settings.static_dir / "favicon.png").open("wb") as fp:
                        shutil.copyfileobj(r.raw, fp)

            settings.name = data["name"]
    except Exception as e:
        logger.exception(e)
        pass


####################################
# File Upload DIR
####################################

UPLOAD_DIR = settings.data_dir / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


####################################
# Cache DIR
####################################

CACHE_DIR = settings.data_dir / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


####################################
# Docs DIR
####################################

settings.docs_dir.mkdir(parents=True, exist_ok=True)

####################################
# OLLAMA_BASE_URL
####################################


OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "")
K8S_FLAG = os.environ.get("K8S_FLAG", "")
USE_OLLAMA_DOCKER = os.environ.get("USE_OLLAMA_DOCKER", "false")

if OLLAMA_BASE_URL == "":
    OLLAMA_BASE_URL = (
        str(settings.ollama_api_base_url)[:-4]
        if settings.ollama_api_base_url.path == "/api"
        else str(settings.ollama_api_base_url)
    )

if settings.env == "prod":
    if OLLAMA_BASE_URL == "/ollama" and not K8S_FLAG:
        if USE_OLLAMA_DOCKER.lower() == "true":
            # if you use all-in-one docker container (Omni WebUI + Ollama)
            # with the docker build arg USE_OLLAMA=true (--build-arg="USE_OLLAMA=true") this only works with http://localhost:11434
            OLLAMA_BASE_URL = "http://localhost:11434"
        else:
            OLLAMA_BASE_URL = "http://host.docker.internal:11434"
    elif K8S_FLAG:
        OLLAMA_BASE_URL = "http://ollama-service.omni-webui.svc.cluster.local:11434"


def separated_env(env_name: str, separator: str = ";"):
    env_value = os.environ.get(env_name, "")
    return [url.strip() for url in env_value.split(separator)] if env_value else []


####################################
# OPENAI_API
####################################
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_API_BASE_URL = "https://api.openai.com/v1"


class BannerModel(BaseModel):
    id: str
    type: str
    title: Optional[str] = None
    content: str
    dismissible: bool
    timestamp: int


####################################
# WEBUI_SECRET_KEY
####################################


####################################
# RAG
####################################

CHROMA_DATA_PATH = f"{DATA_DIR}/vector_db"
CHROMA_TENANT = os.environ.get("CHROMA_TENANT", chromadb.DEFAULT_TENANT)
CHROMA_DATABASE = os.environ.get("CHROMA_DATABASE", chromadb.DEFAULT_DATABASE)
CHROMA_HTTP_HOST = os.environ.get("CHROMA_HTTP_HOST", "")
CHROMA_HTTP_PORT = int(os.environ.get("CHROMA_HTTP_PORT", "8000"))
# Comma-separated list of header=value pairs
CHROMA_HTTP_HEADERS: dict[str, str] | None
if chroma_http_headers := os.getenv("CHROMA_HTTP_HEADERS"):
    CHROMA_HTTP_HEADERS = dict(
        pair.split("=", 1) for pair in chroma_http_headers.split(",")
    )
else:
    CHROMA_HTTP_HEADERS = None
CHROMA_HTTP_SSL = os.environ.get("CHROMA_HTTP_SSL", "false").lower() == "true"
# this uses the model defined in the Dockerfile ENV variable. If you dont use docker or docker based deployments such as k8s, the default embedding model will be used (sentence-transformers/all-MiniLM-L6-v2)

logger.info(f"Embedding model set: {config.rag.embedding_model}")

RAG_EMBEDDING_MODEL_AUTO_UPDATE = (
    os.environ.get("RAG_EMBEDDING_MODEL_AUTO_UPDATE", "").lower() == "true"
)

RAG_EMBEDDING_MODEL_TRUST_REMOTE_CODE = (
    os.environ.get("RAG_EMBEDDING_MODEL_TRUST_REMOTE_CODE", "").lower() == "true"
)

RAG_RERANKING_MODEL_AUTO_UPDATE = (
    os.environ.get("RAG_RERANKING_MODEL_AUTO_UPDATE", "").lower() == "true"
)

RAG_RERANKING_MODEL_TRUST_REMOTE_CODE = (
    os.environ.get("RAG_RERANKING_MODEL_TRUST_REMOTE_CODE", "").lower() == "true"
)


if CHROMA_HTTP_HOST != "":
    CHROMA_CLIENT = chromadb.HttpClient(
        host=CHROMA_HTTP_HOST,
        port=CHROMA_HTTP_PORT,
        headers=CHROMA_HTTP_HEADERS,
        ssl=CHROMA_HTTP_SSL,
        tenant=CHROMA_TENANT,
        database=CHROMA_DATABASE,
        settings=ChromaSettings(allow_reset=True, anonymized_telemetry=False),
    )
else:
    CHROMA_CLIENT = chromadb.PersistentClient(
        path=CHROMA_DATA_PATH,
        settings=ChromaSettings(allow_reset=True, anonymized_telemetry=False),
        tenant=CHROMA_TENANT,
        database=CHROMA_DATABASE,
    )


# device type embedding models - "cpu" (default), "cuda" (nvidia gpu required) or "mps" (apple silicon) - choosing this right can lead to better performance
USE_CUDA = os.getenv("USE_CUDA_DOCKER", "false")

if USE_CUDA.lower() == "true":
    DEVICE_TYPE = "cuda"
else:
    DEVICE_TYPE = "cpu"

####################################
# Transcribe
####################################

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
WHISPER_MODEL_DIR = os.getenv("WHISPER_MODEL_DIR", f"{CACHE_DIR}/whisper/models")
WHISPER_MODEL_AUTO_UPDATE = (
    os.environ.get("WHISPER_MODEL_AUTO_UPDATE", "").lower() == "true"
)
