import asyncio
import importlib.resources
import json
import mimetypes
import os
import time
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import aiohttp
import keepachangelog
from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Request,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from openai import OpenAIError
from pydantic import BaseModel, RootModel
from pydantic_extra_types.semantic_version import SemanticVersion
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import Response

from omni_webui import __version__
from omni_webui._exc import OmniWebUIError
from omni_webui.config import (
    ADMIN_EMAIL,
    API_KEY_ALLOWED_ENDPOINTS,
    # Audio
    AUDIO_STT_ENGINE,
    AUDIO_STT_MODEL,
    AUDIO_STT_OPENAI_API_BASE_URL,
    AUDIO_STT_OPENAI_API_KEY,
    AUDIO_TTS_API_KEY,
    AUDIO_TTS_AZURE_SPEECH_OUTPUT_FORMAT,
    AUDIO_TTS_AZURE_SPEECH_REGION,
    AUDIO_TTS_ENGINE,
    AUDIO_TTS_MODEL,
    AUDIO_TTS_OPENAI_API_BASE_URL,
    AUDIO_TTS_OPENAI_API_KEY,
    AUDIO_TTS_SPLIT_ON,
    AUDIO_TTS_VOICE,
    AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH,
    AUTOCOMPLETE_GENERATION_PROMPT_TEMPLATE,
    # Image
    AUTOMATIC1111_API_AUTH,
    AUTOMATIC1111_BASE_URL,
    AUTOMATIC1111_CFG_SCALE,
    AUTOMATIC1111_SAMPLER,
    AUTOMATIC1111_SCHEDULER,
    BING_SEARCH_V7_ENDPOINT,
    BING_SEARCH_V7_SUBSCRIPTION_KEY,
    BRAVE_SEARCH_API_KEY,
    CACHE_DIR,
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    COMFYUI_API_KEY,
    COMFYUI_BASE_URL,
    COMFYUI_WORKFLOW,
    COMFYUI_WORKFLOW_NODES,
    CONTENT_EXTRACTION_ENGINE,
    CORS_ALLOW_ORIGIN,
    DEFAULT_LOCALE,
    DEFAULT_MODELS,
    DEFAULT_PROMPT_SUGGESTIONS,
    DEFAULT_USER_ROLE,
    # Admin
    ENABLE_ADMIN_CHAT_ACCESS,
    ENABLE_ADMIN_EXPORT,
    ENABLE_API_KEY,
    ENABLE_API_KEY_ENDPOINT_RESTRICTIONS,
    ENABLE_AUTOCOMPLETE_GENERATION,
    ENABLE_CHANNELS,
    ENABLE_COMMUNITY_SHARING,
    ENABLE_EVALUATION_ARENA_MODELS,
    ENABLE_GOOGLE_DRIVE_INTEGRATION,
    ENABLE_IMAGE_GENERATION,
    # WebUI (LDAP)
    ENABLE_LDAP,
    ENABLE_LOGIN_FORM,
    ENABLE_MESSAGE_RATING,
    # WebUI (OAuth)
    ENABLE_OAUTH_ROLE_MANAGEMENT,
    # OpenAI
    ENABLE_RAG_HYBRID_SEARCH,
    ENABLE_RAG_WEB_LOADER_SSL_VERIFICATION,
    ENABLE_RAG_WEB_SEARCH,
    ENABLE_RETRIEVAL_QUERY_GENERATION,
    ENABLE_SEARCH_QUERY_GENERATION,
    ENABLE_SIGNUP,
    ENABLE_TAGS_GENERATION,
    # Misc
    ENV,
    EVALUATION_ARENA_MODELS,
    FRONTEND_BUILD_DIR,
    GOOGLE_DRIVE_API_KEY,
    GOOGLE_DRIVE_CLIENT_ID,
    GOOGLE_PSE_API_KEY,
    GOOGLE_PSE_ENGINE_ID,
    IMAGE_GENERATION_ENGINE,
    IMAGE_GENERATION_MODEL,
    IMAGE_SIZE,
    IMAGE_STEPS,
    IMAGES_OPENAI_API_BASE_URL,
    IMAGES_OPENAI_API_KEY,
    JINA_API_KEY,
    JWT_EXPIRES_IN,
    KAGI_SEARCH_API_KEY,
    LDAP_APP_DN,
    LDAP_APP_PASSWORD,
    LDAP_ATTRIBUTE_FOR_USERNAME,
    LDAP_CA_CERT_FILE,
    LDAP_CIPHERS,
    LDAP_SEARCH_BASE,
    LDAP_SEARCH_FILTERS,
    LDAP_SERVER_HOST,
    LDAP_SERVER_LABEL,
    LDAP_SERVER_PORT,
    LDAP_USE_TLS,
    MODEL_ORDER_LIST,
    MOJEEK_SEARCH_API_KEY,
    OAUTH_ADMIN_ROLES,
    OAUTH_ALLOWED_ROLES,
    OAUTH_EMAIL_CLAIM,
    OAUTH_PICTURE_CLAIM,
    OAUTH_PROVIDERS,
    OAUTH_ROLES_CLAIM,
    OAUTH_USERNAME_CLAIM,
    OLLAMA_API_CONFIGS,
    OLLAMA_BASE_URLS,
    OPENAI_API_BASE_URLS,
    OPENAI_API_CONFIGS,
    OPENAI_API_KEYS,
    PDF_EXTRACT_IMAGES,
    QUERY_GENERATION_PROMPT_TEMPLATE,
    RAG_EMBEDDING_BATCH_SIZE,
    RAG_EMBEDDING_ENGINE,
    RAG_EMBEDDING_MODEL,
    RAG_EMBEDDING_MODEL_AUTO_UPDATE,
    RAG_FILE_MAX_COUNT,
    RAG_FILE_MAX_SIZE,
    RAG_OLLAMA_API_KEY,
    RAG_OLLAMA_BASE_URL,
    RAG_OPENAI_API_BASE_URL,
    RAG_OPENAI_API_KEY,
    RAG_RELEVANCE_THRESHOLD,
    RAG_RERANKING_MODEL,
    RAG_RERANKING_MODEL_AUTO_UPDATE,
    # Retrieval
    RAG_TEMPLATE,
    RAG_TEXT_SPLITTER,
    RAG_TOP_K,
    RAG_WEB_SEARCH_CONCURRENT_REQUESTS,
    RAG_WEB_SEARCH_DOMAIN_FILTER_LIST,
    # Retrieval (Web Search)
    RAG_WEB_SEARCH_ENGINE,
    RAG_WEB_SEARCH_RESULT_COUNT,
    SEARCHAPI_API_KEY,
    SEARCHAPI_ENGINE,
    SEARXNG_QUERY_URL,
    SERPER_API_KEY,
    SERPLY_API_KEY,
    SERPSTACK_API_KEY,
    SERPSTACK_HTTPS,
    SHOW_ADMIN_DETAILS,
    STATIC_DIR,
    TAGS_GENERATION_PROMPT_TEMPLATE,
    # Tasks
    TASK_MODEL,
    TASK_MODEL_EXTERNAL,
    TAVILY_API_KEY,
    TIKA_SERVER_URL,
    TIKTOKEN_ENCODING_NAME,
    TITLE_GENERATION_PROMPT_TEMPLATE,
    TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE,
    USER_PERMISSIONS,
    WEBHOOK_URL,
    # WebUI
    WEBUI_AUTH,
    WEBUI_BANNERS,
    WEBUI_URL,
    WHISPER_MODEL,
    YOUTUBE_LOADER_LANGUAGE,
    YOUTUBE_LOADER_PROXY_URL,
    AppConfig,
    ConfigDepends,
)
from omni_webui.env import (
    ENABLE_WEBSOCKET_SUPPORT,
    OFFLINE_MODE,
    WEBUI_AUTH_TRUSTED_EMAIL_HEADER,
    WEBUI_AUTH_TRUSTED_NAME_HEADER,
    WEBUI_SECRET_KEY,
    WEBUI_SESSION_COOKIE_SAME_SITE,
    WEBUI_SESSION_COOKIE_SECURE,
    EnvDepends,
)
from omni_webui.internal.db import Session
from omni_webui.models import *  # noqa
from omni_webui.models.models import Models
from omni_webui.models.users import Users
from omni_webui.routers import (
    audio,
    auths,
    channels,
    chats,
    configs,
    evaluations,
    files,
    folders,
    groups,
    images,
    knowledge,
    memories,
    models,
    ollama,
    openai,
    prompts,
    retrieval,
    tasks,
    tools,
    users,
    utils,
)
from omni_webui.routers.retrieval import (
    get_ef,
    get_embedding_function,
    get_rf,
)
from omni_webui.settings import SettingsDepends
from omni_webui.socket.main import (
    app as socket_app,
)
from omni_webui.socket.main import (
    periodic_usage_pool_cleanup,
)
from omni_webui.tasks import list_tasks, stop_task  # Import from tasks.py
from omni_webui.utils.access_control import has_access
from omni_webui.utils.auth import (
    decode_token,
    get_admin_user,
    get_verified_user,
)
from omni_webui.utils.chat import (
    chat_completed as chat_completed_handler,
)
from omni_webui.utils.chat import (
    generate_chat_completion as chat_completion_handler,
)
from omni_webui.utils.middleware import process_chat_payload, process_chat_response
from omni_webui.utils.models import (
    check_model_access,
    get_all_base_models,
    get_all_models,
)
from omni_webui.utils.oauth import oauth_manager
from omni_webui.utils.security_headers import SecurityHeadersMiddleware


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except (HTTPException, StarletteHTTPException) as ex:
            if ex.status_code == 404:
                return await super().get_response("index.html", scope)
            else:
                raise ex


logger.info(
    rf"""
  ___                     _  __        __       _      _   _  ___ 
 / _ \  _ __ ___   _ __  (_) \ \      / /  ___ | |__  | | | ||_ _|
| | | || '_ ` _ \ | '_ \ | |  \ \ /\ / /  / _ \| '_ \ | | | | | | 
| |_| || | | | | || | | || |   \ V  V /  |  __/| |_) || |_| | | | 
 \___/ |_| |_| |_||_| |_||_|    \_/\_/    \___||_.__/  \___/ |___|


v{__version__} - building the best open-source AI user interface.

https://github.com/omni-webui/omni-webui
"""
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(periodic_usage_pool_cleanup())
    yield


app = FastAPI(
    docs_url="/docs" if ENV == "dev" else None,
    openapi_url="/openapi.json" if ENV == "dev" else None,
    redoc_url=None,
    lifespan=lifespan,
)

app.state.config = AppConfig()
app.state.config.OLLAMA_BASE_URLS = OLLAMA_BASE_URLS
app.state.config.OLLAMA_API_CONFIGS = OLLAMA_API_CONFIGS

app.state.OLLAMA_MODELS = {}

app.state.config.OPENAI_API_BASE_URLS = OPENAI_API_BASE_URLS
app.state.config.OPENAI_API_KEYS = OPENAI_API_KEYS
app.state.config.OPENAI_API_CONFIGS = OPENAI_API_CONFIGS

app.state.OPENAI_MODELS = {}

app.state.config.WEBUI_URL = WEBUI_URL
app.state.config.ENABLE_SIGNUP = ENABLE_SIGNUP
app.state.config.ENABLE_LOGIN_FORM = ENABLE_LOGIN_FORM

app.state.config.ENABLE_API_KEY = ENABLE_API_KEY
app.state.config.ENABLE_API_KEY_ENDPOINT_RESTRICTIONS = (
    ENABLE_API_KEY_ENDPOINT_RESTRICTIONS
)
app.state.config.API_KEY_ALLOWED_ENDPOINTS = API_KEY_ALLOWED_ENDPOINTS

app.state.config.JWT_EXPIRES_IN = JWT_EXPIRES_IN

app.state.config.SHOW_ADMIN_DETAILS = SHOW_ADMIN_DETAILS
app.state.config.ADMIN_EMAIL = ADMIN_EMAIL


app.state.config.DEFAULT_MODELS = DEFAULT_MODELS
app.state.config.DEFAULT_PROMPT_SUGGESTIONS = DEFAULT_PROMPT_SUGGESTIONS
app.state.config.DEFAULT_USER_ROLE = DEFAULT_USER_ROLE

app.state.config.USER_PERMISSIONS = USER_PERMISSIONS
app.state.config.WEBHOOK_URL = WEBHOOK_URL
app.state.config.BANNERS = WEBUI_BANNERS
app.state.config.MODEL_ORDER_LIST = MODEL_ORDER_LIST


app.state.config.ENABLE_CHANNELS = ENABLE_CHANNELS
app.state.config.ENABLE_COMMUNITY_SHARING = ENABLE_COMMUNITY_SHARING
app.state.config.ENABLE_MESSAGE_RATING = ENABLE_MESSAGE_RATING

app.state.config.ENABLE_EVALUATION_ARENA_MODELS = ENABLE_EVALUATION_ARENA_MODELS
app.state.config.EVALUATION_ARENA_MODELS = EVALUATION_ARENA_MODELS

app.state.config.OAUTH_USERNAME_CLAIM = OAUTH_USERNAME_CLAIM
app.state.config.OAUTH_PICTURE_CLAIM = OAUTH_PICTURE_CLAIM
app.state.config.OAUTH_EMAIL_CLAIM = OAUTH_EMAIL_CLAIM

app.state.config.ENABLE_OAUTH_ROLE_MANAGEMENT = ENABLE_OAUTH_ROLE_MANAGEMENT
app.state.config.OAUTH_ROLES_CLAIM = OAUTH_ROLES_CLAIM
app.state.config.OAUTH_ALLOWED_ROLES = OAUTH_ALLOWED_ROLES
app.state.config.OAUTH_ADMIN_ROLES = OAUTH_ADMIN_ROLES

app.state.config.ENABLE_LDAP = ENABLE_LDAP
app.state.config.LDAP_SERVER_LABEL = LDAP_SERVER_LABEL
app.state.config.LDAP_SERVER_HOST = LDAP_SERVER_HOST
app.state.config.LDAP_SERVER_PORT = LDAP_SERVER_PORT
app.state.config.LDAP_ATTRIBUTE_FOR_USERNAME = LDAP_ATTRIBUTE_FOR_USERNAME
app.state.config.LDAP_APP_DN = LDAP_APP_DN
app.state.config.LDAP_APP_PASSWORD = LDAP_APP_PASSWORD
app.state.config.LDAP_SEARCH_BASE = LDAP_SEARCH_BASE
app.state.config.LDAP_SEARCH_FILTERS = LDAP_SEARCH_FILTERS
app.state.config.LDAP_USE_TLS = LDAP_USE_TLS
app.state.config.LDAP_CA_CERT_FILE = LDAP_CA_CERT_FILE
app.state.config.LDAP_CIPHERS = LDAP_CIPHERS


app.state.AUTH_TRUSTED_EMAIL_HEADER = WEBUI_AUTH_TRUSTED_EMAIL_HEADER
app.state.AUTH_TRUSTED_NAME_HEADER = WEBUI_AUTH_TRUSTED_NAME_HEADER

app.state.TOOLS = {}
app.state.FUNCTIONS = {}

app.state.config.TOP_K = RAG_TOP_K
app.state.config.RELEVANCE_THRESHOLD = RAG_RELEVANCE_THRESHOLD
app.state.config.FILE_MAX_SIZE = RAG_FILE_MAX_SIZE
app.state.config.FILE_MAX_COUNT = RAG_FILE_MAX_COUNT

app.state.config.ENABLE_RAG_HYBRID_SEARCH = ENABLE_RAG_HYBRID_SEARCH
app.state.config.ENABLE_RAG_WEB_LOADER_SSL_VERIFICATION = (
    ENABLE_RAG_WEB_LOADER_SSL_VERIFICATION
)

app.state.config.CONTENT_EXTRACTION_ENGINE = CONTENT_EXTRACTION_ENGINE
app.state.config.TIKA_SERVER_URL = TIKA_SERVER_URL

app.state.config.TEXT_SPLITTER = RAG_TEXT_SPLITTER
app.state.config.TIKTOKEN_ENCODING_NAME = TIKTOKEN_ENCODING_NAME

app.state.config.CHUNK_SIZE = CHUNK_SIZE
app.state.config.CHUNK_OVERLAP = CHUNK_OVERLAP

app.state.config.RAG_EMBEDDING_ENGINE = RAG_EMBEDDING_ENGINE
app.state.config.RAG_EMBEDDING_MODEL = RAG_EMBEDDING_MODEL
app.state.config.RAG_EMBEDDING_BATCH_SIZE = RAG_EMBEDDING_BATCH_SIZE
app.state.config.RAG_RERANKING_MODEL = RAG_RERANKING_MODEL
app.state.config.RAG_TEMPLATE = RAG_TEMPLATE

app.state.config.RAG_OPENAI_API_BASE_URL = RAG_OPENAI_API_BASE_URL
app.state.config.RAG_OPENAI_API_KEY = RAG_OPENAI_API_KEY

app.state.config.RAG_OLLAMA_BASE_URL = RAG_OLLAMA_BASE_URL
app.state.config.RAG_OLLAMA_API_KEY = RAG_OLLAMA_API_KEY

app.state.config.PDF_EXTRACT_IMAGES = PDF_EXTRACT_IMAGES

app.state.config.YOUTUBE_LOADER_LANGUAGE = YOUTUBE_LOADER_LANGUAGE
app.state.config.YOUTUBE_LOADER_PROXY_URL = YOUTUBE_LOADER_PROXY_URL


app.state.config.ENABLE_RAG_WEB_SEARCH = ENABLE_RAG_WEB_SEARCH
app.state.config.RAG_WEB_SEARCH_ENGINE = RAG_WEB_SEARCH_ENGINE
app.state.config.RAG_WEB_SEARCH_DOMAIN_FILTER_LIST = RAG_WEB_SEARCH_DOMAIN_FILTER_LIST

app.state.config.ENABLE_GOOGLE_DRIVE_INTEGRATION = ENABLE_GOOGLE_DRIVE_INTEGRATION
app.state.config.SEARXNG_QUERY_URL = SEARXNG_QUERY_URL
app.state.config.GOOGLE_PSE_API_KEY = GOOGLE_PSE_API_KEY
app.state.config.GOOGLE_PSE_ENGINE_ID = GOOGLE_PSE_ENGINE_ID
app.state.config.BRAVE_SEARCH_API_KEY = BRAVE_SEARCH_API_KEY
app.state.config.KAGI_SEARCH_API_KEY = KAGI_SEARCH_API_KEY
app.state.config.MOJEEK_SEARCH_API_KEY = MOJEEK_SEARCH_API_KEY
app.state.config.SERPSTACK_API_KEY = SERPSTACK_API_KEY
app.state.config.SERPSTACK_HTTPS = SERPSTACK_HTTPS
app.state.config.SERPER_API_KEY = SERPER_API_KEY
app.state.config.SERPLY_API_KEY = SERPLY_API_KEY
app.state.config.TAVILY_API_KEY = TAVILY_API_KEY
app.state.config.SEARCHAPI_API_KEY = SEARCHAPI_API_KEY
app.state.config.SEARCHAPI_ENGINE = SEARCHAPI_ENGINE
app.state.config.JINA_API_KEY = JINA_API_KEY
app.state.config.BING_SEARCH_V7_ENDPOINT = BING_SEARCH_V7_ENDPOINT
app.state.config.BING_SEARCH_V7_SUBSCRIPTION_KEY = BING_SEARCH_V7_SUBSCRIPTION_KEY

app.state.config.RAG_WEB_SEARCH_RESULT_COUNT = RAG_WEB_SEARCH_RESULT_COUNT
app.state.config.RAG_WEB_SEARCH_CONCURRENT_REQUESTS = RAG_WEB_SEARCH_CONCURRENT_REQUESTS

app.state.EMBEDDING_FUNCTION = None
app.state.ef = None
app.state.rf = None

app.state.YOUTUBE_LOADER_TRANSLATION = None


try:
    app.state.ef = get_ef(
        app.state.config.RAG_EMBEDDING_ENGINE,
        app.state.config.RAG_EMBEDDING_MODEL,
        RAG_EMBEDDING_MODEL_AUTO_UPDATE,
    )

    app.state.rf = get_rf(
        app.state.config.RAG_RERANKING_MODEL,
        RAG_RERANKING_MODEL_AUTO_UPDATE,
    )
except Exception as e:
    logger.error(f"Error updating models: {e}")


app.state.EMBEDDING_FUNCTION = get_embedding_function(
    app.state.config.RAG_EMBEDDING_ENGINE,
    app.state.config.RAG_EMBEDDING_MODEL,
    app.state.ef,
    (
        app.state.config.RAG_OPENAI_API_BASE_URL
        if app.state.config.RAG_EMBEDDING_ENGINE == "openai"
        else app.state.config.RAG_OLLAMA_BASE_URL
    ),
    (
        app.state.config.RAG_OPENAI_API_KEY
        if app.state.config.RAG_EMBEDDING_ENGINE == "openai"
        else app.state.config.RAG_OLLAMA_API_KEY
    ),
    app.state.config.RAG_EMBEDDING_BATCH_SIZE,
)

app.state.config.IMAGE_GENERATION_ENGINE = IMAGE_GENERATION_ENGINE
app.state.config.ENABLE_IMAGE_GENERATION = ENABLE_IMAGE_GENERATION

app.state.config.IMAGES_OPENAI_API_BASE_URL = IMAGES_OPENAI_API_BASE_URL
app.state.config.IMAGES_OPENAI_API_KEY = IMAGES_OPENAI_API_KEY

app.state.config.IMAGE_GENERATION_MODEL = IMAGE_GENERATION_MODEL

app.state.config.AUTOMATIC1111_BASE_URL = AUTOMATIC1111_BASE_URL
app.state.config.AUTOMATIC1111_API_AUTH = AUTOMATIC1111_API_AUTH
app.state.config.AUTOMATIC1111_CFG_SCALE = AUTOMATIC1111_CFG_SCALE
app.state.config.AUTOMATIC1111_SAMPLER = AUTOMATIC1111_SAMPLER
app.state.config.AUTOMATIC1111_SCHEDULER = AUTOMATIC1111_SCHEDULER
app.state.config.COMFYUI_BASE_URL = COMFYUI_BASE_URL
app.state.config.COMFYUI_API_KEY = COMFYUI_API_KEY
app.state.config.COMFYUI_WORKFLOW = COMFYUI_WORKFLOW
app.state.config.COMFYUI_WORKFLOW_NODES = COMFYUI_WORKFLOW_NODES

app.state.config.IMAGE_SIZE = IMAGE_SIZE
app.state.config.IMAGE_STEPS = IMAGE_STEPS

app.state.config.STT_OPENAI_API_BASE_URL = AUDIO_STT_OPENAI_API_BASE_URL
app.state.config.STT_OPENAI_API_KEY = AUDIO_STT_OPENAI_API_KEY
app.state.config.STT_ENGINE = AUDIO_STT_ENGINE
app.state.config.STT_MODEL = AUDIO_STT_MODEL

app.state.config.WHISPER_MODEL = WHISPER_MODEL

app.state.config.TTS_OPENAI_API_BASE_URL = AUDIO_TTS_OPENAI_API_BASE_URL
app.state.config.TTS_OPENAI_API_KEY = AUDIO_TTS_OPENAI_API_KEY
app.state.config.TTS_ENGINE = AUDIO_TTS_ENGINE
app.state.config.TTS_MODEL = AUDIO_TTS_MODEL
app.state.config.TTS_VOICE = AUDIO_TTS_VOICE
app.state.config.TTS_API_KEY = AUDIO_TTS_API_KEY
app.state.config.TTS_SPLIT_ON = AUDIO_TTS_SPLIT_ON


app.state.config.TTS_AZURE_SPEECH_REGION = AUDIO_TTS_AZURE_SPEECH_REGION
app.state.config.TTS_AZURE_SPEECH_OUTPUT_FORMAT = AUDIO_TTS_AZURE_SPEECH_OUTPUT_FORMAT


app.state.faster_whisper_model = None
app.state.speech_synthesiser = None
app.state.speech_speaker_embeddings_dataset = None


app.state.config.TASK_MODEL = TASK_MODEL
app.state.config.TASK_MODEL_EXTERNAL = TASK_MODEL_EXTERNAL


app.state.config.ENABLE_SEARCH_QUERY_GENERATION = ENABLE_SEARCH_QUERY_GENERATION
app.state.config.ENABLE_RETRIEVAL_QUERY_GENERATION = ENABLE_RETRIEVAL_QUERY_GENERATION
app.state.config.ENABLE_AUTOCOMPLETE_GENERATION = ENABLE_AUTOCOMPLETE_GENERATION
app.state.config.ENABLE_TAGS_GENERATION = ENABLE_TAGS_GENERATION


app.state.config.TITLE_GENERATION_PROMPT_TEMPLATE = TITLE_GENERATION_PROMPT_TEMPLATE
app.state.config.TAGS_GENERATION_PROMPT_TEMPLATE = TAGS_GENERATION_PROMPT_TEMPLATE
app.state.config.TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE = (
    TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE
)
app.state.config.QUERY_GENERATION_PROMPT_TEMPLATE = QUERY_GENERATION_PROMPT_TEMPLATE
app.state.config.AUTOCOMPLETE_GENERATION_PROMPT_TEMPLATE = (
    AUTOCOMPLETE_GENERATION_PROMPT_TEMPLATE
)
app.state.config.AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH = (
    AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH
)


app.state.MODELS = {}


class RedirectMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Check if the request is a GET request
        if request.method == "GET":
            path = request.url.path
            query_params = dict(parse_qs(urlparse(str(request.url)).query))

            # Check for the specific watch path and the presence of 'v' parameter
            if path.endswith("/watch") and "v" in query_params:
                video_id = query_params["v"][0]  # Extract the first 'v' parameter
                encoded_video_id = urlencode({"youtube": video_id})
                redirect_url = f"/?{encoded_video_id}"
                return RedirectResponse(url=redirect_url)

        # Proceed with the normal flow of other requests
        response = await call_next(request)
        return response


# Add the middleware to the app
app.add_middleware(RedirectMiddleware)
app.add_middleware(SecurityHeadersMiddleware)


@app.middleware("http")
async def commit_session_after_request(request: Request, call_next):
    response = await call_next(request)
    # log.debug("Commit session after request")
    Session.commit()
    return response


@app.middleware("http")
async def check_url(request: Request, call_next):
    start_time = int(time.time())
    request.state.enable_api_key = app.state.config.ENABLE_API_KEY
    response = await call_next(request)
    process_time = int(time.time()) - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


@app.middleware("http")
async def inspect_websocket(request: Request, call_next):
    if (
        "/ws/socket.io" in request.url.path
        and request.query_params.get("transport") == "websocket"
    ):
        upgrade = (request.headers.get("Upgrade") or "").lower()
        connection = (request.headers.get("Connection") or "").lower().split(",")
        # Check that there's the correct headers for an upgrade, else reject the connection
        # This is to work around this upstream issue: https://github.com/miguelgrinberg/python-engineio/issues/367
        if upgrade != "websocket" or "upgrade" not in connection:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"detail": "Invalid WebSocket upgrade request"},
            )
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGIN,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.mount("/ws", socket_app)
app.include_router(ollama.router, prefix="/ollama", tags=["ollama"])
app.include_router(openai.router, prefix="/openai", tags=["openai"])
app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["tasks"])
app.include_router(images.router, prefix="/api/v1/images", tags=["images"])
app.include_router(audio.router, prefix="/api/v1/audio", tags=["audio"])
app.include_router(retrieval.router, prefix="/api/v1/retrieval", tags=["retrieval"])
app.include_router(configs.router, prefix="/api/v1/configs", tags=["configs"])
app.include_router(auths.router, prefix="/api/v1/auths", tags=["auths"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
app.include_router(channels.router, prefix="/api/v1/channels", tags=["channels"])
app.include_router(chats.router, prefix="/api/v1/chats", tags=["chats"])
app.include_router(models.router, prefix="/api/v1/models", tags=["models"])
app.include_router(knowledge.router, prefix="/api/v1/knowledge", tags=["knowledge"])
app.include_router(prompts.router, prefix="/api/v1/prompts", tags=["prompts"])
app.include_router(tools.router, prefix="/api/v1/tools", tags=["tools"])
app.include_router(memories.router, prefix="/api/v1/memories", tags=["memories"])
app.include_router(folders.router, prefix="/api/v1/folders", tags=["folders"])
app.include_router(groups.router, prefix="/api/v1/groups", tags=["groups"])
app.include_router(files.router, prefix="/api/v1/files", tags=["files"])
app.include_router(
    evaluations.router, prefix="/api/v1/evaluations", tags=["evaluations"]
)
app.include_router(utils.router, prefix="/api/v1/utils", tags=["utils"])


@app.get("/api/models")
async def get_models(
    request: Request,
    config: ConfigDepends,
    env: EnvDepends,
    user=Depends(get_verified_user),
):
    def get_filtered_models(models, user):
        filtered_models = []
        for model in models:
            if model.get("arena"):
                if has_access(
                    user.id,
                    type="read",
                    access_control=model.get("info", {})
                    .get("meta", {})
                    .get("access_control", {}),
                ):
                    filtered_models.append(model)
                continue

            model_info = Models.get_model_by_id(model["id"])
            if model_info:
                if user.id == model_info.user_id or has_access(
                    user.id, type="read", access_control=model_info.access_control
                ):
                    filtered_models.append(model)

        return filtered_models

    models = await get_all_models(request, config)

    model_order_list = request.app.state.config.MODEL_ORDER_LIST
    if model_order_list:
        model_order_dict = {model_id: i for i, model_id in enumerate(model_order_list)}
        # Sort models by order list priority, with fallback for those not in the list
        models.sort(
            key=lambda x: (model_order_dict.get(x["id"], float("inf")), x["name"])
        )

    # Filter out models that the user does not have access to
    if user.role == "user" and not env.bypass_model_access_control:
        models = get_filtered_models(models, user)

    logger.debug(
        f"/api/models returned filtered models accessible to the user: {json.dumps([model['id'] for model in models])}"
    )
    return {"data": models}


@app.get("/api/models/base")
async def get_base_models(
    request: Request, config: ConfigDepends, user=Depends(get_admin_user)
):
    models = await get_all_base_models(request, config)
    return {"data": models}


@app.post("/api/chat/completions")
async def chat_completion(
    request: Request,
    form_data: dict,
    env: EnvDepends,
    config: ConfigDepends,
    settings: SettingsDepends,
    user=Depends(get_verified_user),
):
    if not request.app.state.MODELS:
        await get_all_models(request, config)

    tasks = form_data.pop("background_tasks", None)
    model_id = form_data.get("model", None)
    if model_id not in request.app.state.MODELS:
        raise Exception("Model not found")
    model = request.app.state.MODELS[model_id]

    # Check if user has access to the model
    if not env.bypass_model_access_control and user.role == "user":
        check_model_access(user, model)

    metadata = {
        "user_id": user.id,
        "chat_id": form_data.pop("chat_id", None),
        "message_id": form_data.pop("id", None),
        "session_id": form_data.pop("session_id", None),
        "tool_ids": form_data.get("tool_ids", None),
        "files": form_data.get("files", None),
        "features": form_data.get("features", None),
    }
    form_data["metadata"] = metadata

    form_data, events = await process_chat_payload(
        request, form_data, metadata, user, model
    )

    response = await chat_completion_handler(request, form_data, user)
    return await process_chat_response(
        request, response, form_data, user, events, metadata, tasks, settings
    )


# Alias for chat_completion (Legacy)
generate_chat_completions = chat_completion
generate_chat_completion = chat_completion


@app.post("/api/chat/completed")
async def chat_completed(
    request: Request,
    form_data: dict,
    config: ConfigDepends,
    user=Depends(get_verified_user),
):
    return await chat_completed_handler(request, form_data, user, config)


@app.post("/api/tasks/stop/{task_id}")
async def stop_task_endpoint(task_id: str, user=Depends(get_verified_user)):
    try:
        result = await stop_task(task_id)  # Use the function from tasks.py
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@app.get("/api/tasks")
async def list_tasks_endpoint(user=Depends(get_verified_user)):
    return {"tasks": list_tasks()}  # Use the function from tasks.py


@app.get("/api/config")
async def get_app_config(request: Request, settings: SettingsDepends):
    user = None
    if "token" in request.cookies:
        token = request.cookies.get("token")
        data = decode_token(token)
        if data is not None and "id" in data:
            user = Users.get_user_by_id(data["id"])

    onboarding = False
    if user is None:
        user_count = Users.get_num_users()
        onboarding = user_count == 0

    return {
        **({"onboarding": True} if onboarding else {}),
        "status": True,
        "name": settings.title,
        "version": __version__,
        "default_locale": str(DEFAULT_LOCALE),
        "oauth": {
            "providers": {
                name: config.get("name", name)
                for name, config in OAUTH_PROVIDERS.items()
            }
        },
        "features": {
            "auth": WEBUI_AUTH,
            "auth_trusted_header": bool(app.state.AUTH_TRUSTED_EMAIL_HEADER),
            "enable_ldap": app.state.config.ENABLE_LDAP,
            "enable_api_key": app.state.config.ENABLE_API_KEY,
            "enable_signup": app.state.config.ENABLE_SIGNUP,
            "enable_login_form": app.state.config.ENABLE_LOGIN_FORM,
            "enable_websocket": ENABLE_WEBSOCKET_SUPPORT,
            **(
                {
                    "enable_channels": app.state.config.ENABLE_CHANNELS,
                    "enable_web_search": app.state.config.ENABLE_RAG_WEB_SEARCH,
                    "enable_google_drive_integration": app.state.config.ENABLE_GOOGLE_DRIVE_INTEGRATION,
                    "enable_image_generation": app.state.config.ENABLE_IMAGE_GENERATION,
                    "enable_community_sharing": app.state.config.ENABLE_COMMUNITY_SHARING,
                    "enable_message_rating": app.state.config.ENABLE_MESSAGE_RATING,
                    "enable_admin_export": ENABLE_ADMIN_EXPORT,
                    "enable_admin_chat_access": ENABLE_ADMIN_CHAT_ACCESS,
                }
                if user is not None
                else {}
            ),
        },
        "google_drive": {
            "client_id": GOOGLE_DRIVE_CLIENT_ID.value,
            "api_key": GOOGLE_DRIVE_API_KEY.value,
        },
        **(
            {
                "default_models": app.state.config.DEFAULT_MODELS,
                "default_prompt_suggestions": app.state.config.DEFAULT_PROMPT_SUGGESTIONS,
                "audio": {
                    "tts": {
                        "engine": app.state.config.TTS_ENGINE,
                        "voice": app.state.config.TTS_VOICE,
                        "split_on": app.state.config.TTS_SPLIT_ON,
                    },
                    "stt": {
                        "engine": app.state.config.STT_ENGINE,
                    },
                },
                "file": {
                    "max_size": app.state.config.FILE_MAX_SIZE,
                    "max_count": app.state.config.FILE_MAX_COUNT,
                },
                "permissions": {**app.state.config.USER_PERMISSIONS},
            }
            if user is not None
            else {}
        ),
    }


class UrlForm(BaseModel):
    url: str


@app.get("/api/webhook")
async def get_webhook_url(user=Depends(get_admin_user)):
    return {
        "url": app.state.config.WEBHOOK_URL,
    }


@app.post("/api/webhook")
async def update_webhook_url(form_data: UrlForm, user=Depends(get_admin_user)):
    app.state.config.WEBHOOK_URL = form_data.url
    app.state.WEBHOOK_URL = app.state.config.WEBHOOK_URL
    return {"url": app.state.config.WEBHOOK_URL}


@app.get("/api/version")
async def get_app_version():
    return {
        "version": __version__,
    }


@app.get("/api/version/updates")
async def get_app_latest_release_version():
    if OFFLINE_MODE:
        logger.debug(
            "Offline mode is enabled, returning current version as latest version"
        )
        return {"current": __version__, "latest": __version__}
    timeout = aiohttp.ClientTimeout(total=1)
    async with aiohttp.ClientSession(timeout=timeout, trust_env=True) as session:
        async with session.get(
            "https://api.github.com/repos/open-webui/open-webui/releases/latest"
        ) as response:
            response.raise_for_status()
            data = await response.json()
            latest_version = data["tag_name"]

            return {"current": __version__, "latest": latest_version[1:]}


class ChangelogEntry(BaseModel):
    title: str
    content: str


class ChangelogItem(BaseModel):
    class Metadata(BaseModel):
        release_date: date

    added: list[ChangelogEntry] | None = None
    changed: list[ChangelogEntry] | None = None
    deprecated: list[ChangelogEntry] | None = None
    removed: list[ChangelogEntry] | None = None
    fixed: list[ChangelogEntry] | None = None
    security: list[ChangelogEntry] | None = None
    metadata: Metadata


@app.get(
    "/api/changelog",
    response_model=RootModel[dict[SemanticVersion, ChangelogItem]],
    response_model_exclude_none=True,
)
async def get_app_changelog():
    changelog_path = Path(str(importlib.resources.files("omni_webui") / "CHANGELOG.md"))
    if not changelog_path.exists():
        return {}
    changelog = keepachangelog.to_dict(str(changelog_path))
    for item in changelog.values():
        for key in ("added", "changed", "deprecated", "removed", "fixed", "security"):
            if key in item:
                texts = []
                for text in item[key]:
                    try:
                        title, content = text.split(":", 1)
                    except ValueError:
                        title, content = "", text
                    texts.append(
                        {"title": title.strip("**"), "content": content.strip()}
                    )
                item[key] = texts
    return changelog


# SessionMiddleware is used by authlib for oauth
if len(OAUTH_PROVIDERS) > 0:
    app.add_middleware(
        SessionMiddleware,
        secret_key=WEBUI_SECRET_KEY,
        session_cookie="oui-session",
        same_site=WEBUI_SESSION_COOKIE_SAME_SITE,
        https_only=WEBUI_SESSION_COOKIE_SECURE,
    )


@app.get("/oauth/{provider}/login")
async def oauth_login(provider: str, request: Request):
    return await oauth_manager.handle_login(provider, request)


# OAuth login logic is as follows:
# 1. Attempt to find a user with matching subject ID, tied to the provider
# 2. If OAUTH_MERGE_ACCOUNTS_BY_EMAIL is true, find a user with the email address provided via OAuth
#    - This is considered insecure in general, as OAuth providers do not always verify email addresses
# 3. If there is no user, and ENABLE_OAUTH_SIGNUP is true, create a user
#    - Email addresses are considered unique, so we fail registration if the email address is already taken
@app.get("/oauth/{provider}/callback")
async def oauth_callback(
    provider: str, request: Request, response: Response, settings: SettingsDepends
):
    return await oauth_manager.handle_callback(provider, request, response, settings)


@app.get("/manifest.json")
async def get_manifest_json(env: EnvDepends):
    return {
        "name": env.webui_name,
        "short_name": env.webui_name,
        "description": "Open WebUI is an open, extensible, user-friendly interface for AI that adapts to your workflow.",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#343541",
        "orientation": "natural",
        "icons": [
            {
                "src": "/static/logo.png",
                "type": "image/png",
                "sizes": "500x500",
                "purpose": "any",
            },
            {
                "src": "/static/logo.png",
                "type": "image/png",
                "sizes": "500x500",
                "purpose": "maskable",
            },
        ],
    }


@app.get("/opensearch.xml")
async def get_opensearch_xml(env: EnvDepends):
    xml_content = rf"""
    <OpenSearchDescription xmlns="http://a9.com/-/spec/opensearch/1.1/" xmlns:moz="http://www.mozilla.org/2006/browser/search/">
    <ShortName>{env.webui_name}</ShortName>
    <Description>Search {env.webui_name}</Description>
    <InputEncoding>UTF-8</InputEncoding>
    <Image width="16" height="16" type="image/x-icon">{app.state.config.WEBUI_URL}/static/favicon.png</Image>
    <Url type="text/html" method="get" template="{app.state.config.WEBUI_URL}/?q={"{searchTerms}"}"/>
    <moz:SearchForm>{app.state.config.WEBUI_URL}</moz:SearchForm>
    </OpenSearchDescription>
    """
    return Response(content=xml_content, media_type="application/xml")


@app.get("/health")
async def healthcheck():
    return {"status": True}


@app.get("/health/db")
async def healthcheck_with_db():
    Session.execute(text("SELECT 1;")).all()
    return {"status": True}


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/cache", StaticFiles(directory=CACHE_DIR), name="cache")

if os.path.exists(FRONTEND_BUILD_DIR):
    mimetypes.add_type("text/javascript", ".js")
    app.mount(
        "/",
        SPAStaticFiles(directory=FRONTEND_BUILD_DIR, html=True),
        name="spa-static-files",
    )
else:
    logger.warning(
        f"Frontend build directory not found at '{FRONTEND_BUILD_DIR}'. Serving API only."
    )


@app.exception_handler(OpenAIError)
async def openai_exception_handler(request: Request, exc: OpenAIError):
    return JSONResponse(
        status_code=200,
        content={"detail": str(exc)},
    )


@app.exception_handler(OmniWebUIError)
async def omni_webui_exception_handler(request: Request, exc: OmniWebUIError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": exc.detail},
    )


@app.exception_handler(Exception)
async def exception_handler(request: Request, exc: OmniWebUIError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc)},
    )
