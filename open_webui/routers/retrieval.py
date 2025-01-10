"""Retrieval router."""

import json
import logging
import os
import shutil
import uuid
from datetime import datetime
from typing import List, Optional

import tiktoken
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
)
from langchain.text_splitter import RecursiveCharacterTextSplitter, TokenTextSplitter
from langchain_core.documents import Document
from loguru import logger
from pydantic import BaseModel

from open_webui.config import ConfigData, ConfigDBDep, ConfigDep
from open_webui.constants import ERROR_MESSAGES
from open_webui.env import DEVICE_TYPE, env
from open_webui.models import SessionDep
from open_webui.models.file import File as FileModel
from open_webui.models.knowledge import Knowledges
from open_webui.retrieval.loaders.main import Loader
from open_webui.retrieval.loaders.youtube import YoutubeLoader
from open_webui.retrieval.utils import (
    get_embedding_function,
    get_model_path,
    query_collection,
    query_collection_with_hybrid_search,
    query_doc,
    query_doc_with_hybrid_search,
)
from open_webui.retrieval.vector.connector import VECTOR_DB_CLIENT
from open_webui.retrieval.vector.main import VectorItem
from open_webui.retrieval.web.bing import search_bing
from open_webui.retrieval.web.brave import search_brave
from open_webui.retrieval.web.duckduckgo import search_duckduckgo
from open_webui.retrieval.web.google_pse import search_google_pse
from open_webui.retrieval.web.jina_search import search_jina
from open_webui.retrieval.web.kagi import search_kagi
from open_webui.retrieval.web.main import SearchResult
from open_webui.retrieval.web.mojeek import search_mojeek
from open_webui.retrieval.web.searchapi import search_searchapi
from open_webui.retrieval.web.searxng import search_searxng
from open_webui.retrieval.web.serper import search_serper
from open_webui.retrieval.web.serply import search_serply
from open_webui.retrieval.web.serpstack import search_serpstack
from open_webui.retrieval.web.tavily import search_tavily
from open_webui.retrieval.web.utils import get_web_loader
from open_webui.utils.auth import get_admin_user, get_verified_user
from open_webui.utils.misc import (
    calculate_sha256_string,
)


def get_ef(
    engine: str,
    embedding_model: str,
    auto_update: bool = False,
):
    """Get the embedding function."""
    ef = None
    if embedding_model and engine == "":
        from sentence_transformers import SentenceTransformer

        try:
            ef = SentenceTransformer(
                get_model_path(embedding_model, auto_update),
                device=DEVICE_TYPE,
                trust_remote_code=env.RAG_EMBEDDING_MODEL_TRUST_REMOTE_CODE,
            )
        except Exception as e:
            logger.debug(f"Error loading SentenceTransformer: {e}")

    return ef


def get_rf(
    reranking_model: str,
    auto_update: bool = False,
):
    """Get the reranking function."""
    rf = None
    if reranking_model:
        if any(model in reranking_model for model in ["jinaai/jina-colbert-v2"]):
            try:
                from open_webui.retrieval.models.colbert import ColBERT

                rf = ColBERT(
                    get_model_path(reranking_model, auto_update),
                    env="docker" if env.DOCKER else None,
                )

            except Exception as e:
                logger.error(f"ColBERT: {e}")
                raise e
        else:
            import sentence_transformers

            try:
                rf = sentence_transformers.CrossEncoder(
                    get_model_path(reranking_model, auto_update),
                    device=DEVICE_TYPE,
                    trust_remote_code=env.RAG_RERANKING_MODEL_TRUST_REMOTE_CODE,
                )
            except Exception as e:
                logger.error("CrossEncoder error")
                raise e
    return rf


router = APIRouter()


class CollectionNameForm(BaseModel):
    """Collection name form."""

    collection_name: str | None = None


class ProcessUrlForm(CollectionNameForm):
    """Process URL form."""

    url: str


class SearchForm(CollectionNameForm):
    """Search form."""

    query: str


@router.get("/")
async def get_status(request: Request, config: ConfigDep):
    """Get status."""
    return {
        "status": True,
        "chunk_size": config.rag.chunk_size,
        "chunk_overlap": request.app.state.config.CHUNK_OVERLAP,
        "template": config.rag.template,
        "embedding_engine": request.app.state.config.RAG_EMBEDDING_ENGINE,
        "embedding_model": request.app.state.config.RAG_EMBEDDING_MODEL,
        "reranking_model": request.app.state.config.RAG_RERANKING_MODEL,
        "embedding_batch_size": request.app.state.config.RAG_EMBEDDING_BATCH_SIZE,
    }


@router.get("/embedding")
async def get_embedding_config(request: Request, user=Depends(get_admin_user)):
    """Get embedding config."""
    return {
        "status": True,
        "embedding_engine": request.app.state.config.RAG_EMBEDDING_ENGINE,
        "embedding_model": request.app.state.config.RAG_EMBEDDING_MODEL,
        "embedding_batch_size": request.app.state.config.RAG_EMBEDDING_BATCH_SIZE,
        "openai_config": {
            "url": request.app.state.config.RAG_OPENAI_API_BASE_URL,
            "key": request.app.state.config.RAG_OPENAI_API_KEY,
        },
        "ollama_config": {
            "url": request.app.state.config.RAG_OLLAMA_BASE_URL,
            "key": request.app.state.config.RAG_OLLAMA_API_KEY,
        },
    }


@router.get("/reranking")
async def get_reraanking_config(request: Request, user=Depends(get_admin_user)):
    """Get reranking config."""
    return {
        "status": True,
        "reranking_model": request.app.state.config.RAG_RERANKING_MODEL,
    }


class OpenAIConfigForm(BaseModel):
    """OpenAI Config Form."""

    url: str
    key: str


class OllamaConfigForm(BaseModel):
    """Ollama Config Form."""

    url: str
    key: str


class EmbeddingModelUpdateForm(BaseModel):
    """Embedding Model Update Form."""

    openai_config: Optional[OpenAIConfigForm] = None
    ollama_config: Optional[OllamaConfigForm] = None
    embedding_engine: str
    embedding_model: str
    embedding_batch_size: Optional[int] = 1


@router.post("/embedding/update")
async def update_embedding_config(
    request: Request, form_data: EmbeddingModelUpdateForm, user=Depends(get_admin_user)
):
    """Update embedding config."""
    logger.info(
        f"Updating embedding model: {request.app.state.config.RAG_EMBEDDING_MODEL} to {form_data.embedding_model}"
    )
    try:
        request.app.state.config.RAG_EMBEDDING_ENGINE = form_data.embedding_engine
        request.app.state.config.RAG_EMBEDDING_MODEL = form_data.embedding_model

        if request.app.state.config.RAG_EMBEDDING_ENGINE in ["ollama", "openai"]:
            if form_data.openai_config is not None:
                request.app.state.config.RAG_OPENAI_API_BASE_URL = (
                    form_data.openai_config.url
                )
                request.app.state.config.RAG_OPENAI_API_KEY = (
                    form_data.openai_config.key
                )

            if form_data.ollama_config is not None:
                request.app.state.config.RAG_OLLAMA_BASE_URL = (
                    form_data.ollama_config.url
                )
                request.app.state.config.RAG_OLLAMA_API_KEY = (
                    form_data.ollama_config.key
                )

            request.app.state.config.RAG_EMBEDDING_BATCH_SIZE = (
                form_data.embedding_batch_size
            )

        request.app.state.ef = get_ef(
            request.app.state.config.RAG_EMBEDDING_ENGINE,
            request.app.state.config.RAG_EMBEDDING_MODEL,
        )

        request.app.state.EMBEDDING_FUNCTION = get_embedding_function(
            request.app.state.config.RAG_EMBEDDING_ENGINE,
            request.app.state.config.RAG_EMBEDDING_MODEL,
            request.app.state.ef,
            (
                request.app.state.config.RAG_OPENAI_API_BASE_URL
                if request.app.state.config.RAG_EMBEDDING_ENGINE == "openai"
                else request.app.state.config.RAG_OLLAMA_BASE_URL
            ),
            (
                request.app.state.config.RAG_OPENAI_API_KEY
                if request.app.state.config.RAG_EMBEDDING_ENGINE == "openai"
                else request.app.state.config.RAG_OLLAMA_API_KEY
            ),
            request.app.state.config.RAG_EMBEDDING_BATCH_SIZE,
        )

        return {
            "status": True,
            "embedding_engine": request.app.state.config.RAG_EMBEDDING_ENGINE,
            "embedding_model": request.app.state.config.RAG_EMBEDDING_MODEL,
            "embedding_batch_size": request.app.state.config.RAG_EMBEDDING_BATCH_SIZE,
            "openai_config": {
                "url": request.app.state.config.RAG_OPENAI_API_BASE_URL,
                "key": request.app.state.config.RAG_OPENAI_API_KEY,
            },
            "ollama_config": {
                "url": request.app.state.config.RAG_OLLAMA_BASE_URL,
                "key": request.app.state.config.RAG_OLLAMA_API_KEY,
            },
        }
    except Exception as e:
        logger.exception(f"Problem updating embedding model: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


class RerankingModelUpdateForm(BaseModel):
    """Reranking model update form."""

    reranking_model: str


@router.post("/reranking/update")
async def update_reranking_config(
    request: Request, form_data: RerankingModelUpdateForm, user=Depends(get_admin_user)
):
    """Update reranking config."""
    logger.info(
        f"Updating reranking model: {request.app.state.config.RAG_RERANKING_MODEL} to {form_data.reranking_model}"
    )
    try:
        request.app.state.config.RAG_RERANKING_MODEL = form_data.reranking_model

        try:
            request.app.state.rf = get_rf(
                request.app.state.config.RAG_RERANKING_MODEL,
                True,
            )
        except Exception as e:
            logger.error(f"Error loading reranking model: {e}")
            request.app.state.config.ENABLE_RAG_HYBRID_SEARCH = False

        return {
            "status": True,
            "reranking_model": request.app.state.config.RAG_RERANKING_MODEL,
        }
    except Exception as e:
        logger.exception(f"Problem updating reranking model: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/config")
async def get_rag_config(
    request: Request, config: ConfigDep, user=Depends(get_admin_user)
):
    """Get RAG config."""
    return {
        "status": True,
        "pdf_extract_images": request.app.state.config.PDF_EXTRACT_IMAGES,
        "enable_google_drive_integration": request.app.state.config.ENABLE_GOOGLE_DRIVE_INTEGRATION,
        "content_extraction": {
            "engine": request.app.state.config.CONTENT_EXTRACTION_ENGINE,
            "tika_server_url": request.app.state.config.TIKA_SERVER_URL,
        },
        "chunk": {
            "text_splitter": request.app.state.config.TEXT_SPLITTER,
            "chunk_size": config.rag.chunk_size,
            "chunk_overlap": request.app.state.config.CHUNK_OVERLAP,
        },
        "file": {
            "max_size": request.app.state.config.FILE_MAX_SIZE,
            "max_count": request.app.state.config.FILE_MAX_COUNT,
        },
        "youtube": {
            "language": request.app.state.config.YOUTUBE_LOADER_LANGUAGE,
            "translation": request.app.state.YOUTUBE_LOADER_TRANSLATION,
            "proxy_url": request.app.state.config.YOUTUBE_LOADER_PROXY_URL,
        },
        "web": {
            "web_loader_ssl_verification": request.app.state.config.ENABLE_RAG_WEB_LOADER_SSL_VERIFICATION,
            "search": {
                "enabled": request.app.state.config.ENABLE_RAG_WEB_SEARCH,
                "drive": request.app.state.config.ENABLE_GOOGLE_DRIVE_INTEGRATION,
                "engine": request.app.state.config.RAG_WEB_SEARCH_ENGINE,
                "searxng_query_url": request.app.state.config.SEARXNG_QUERY_URL,
                "google_pse_api_key": request.app.state.config.GOOGLE_PSE_API_KEY,
                "google_pse_engine_id": request.app.state.config.GOOGLE_PSE_ENGINE_ID,
                "brave_search_api_key": request.app.state.config.BRAVE_SEARCH_API_KEY,
                "kagi_search_api_key": request.app.state.config.KAGI_SEARCH_API_KEY,
                "mojeek_search_api_key": request.app.state.config.MOJEEK_SEARCH_API_KEY,
                "serpstack_api_key": request.app.state.config.SERPSTACK_API_KEY,
                "serpstack_https": request.app.state.config.SERPSTACK_HTTPS,
                "serper_api_key": request.app.state.config.SERPER_API_KEY,
                "serply_api_key": request.app.state.config.SERPLY_API_KEY,
                "tavily_api_key": request.app.state.config.TAVILY_API_KEY,
                "searchapi_api_key": request.app.state.config.SEARCHAPI_API_KEY,
                "seaarchapi_engine": request.app.state.config.SEARCHAPI_ENGINE,
                "jina_api_key": request.app.state.config.JINA_API_KEY,
                "bing_search_v7_endpoint": request.app.state.config.BING_SEARCH_V7_ENDPOINT,
                "bing_search_v7_subscription_key": request.app.state.config.BING_SEARCH_V7_SUBSCRIPTION_KEY,
                "result_count": request.app.state.config.RAG_WEB_SEARCH_RESULT_COUNT,
                "concurrent_requests": request.app.state.config.RAG_WEB_SEARCH_CONCURRENT_REQUESTS,
            },
        },
    }


class FileConfig(BaseModel):
    """File config form."""

    max_size: Optional[int] = None
    max_count: Optional[int] = None


class ContentExtractionConfig(BaseModel):
    """Content extraction config form."""

    engine: str = ""
    tika_server_url: Optional[str] = None


class ChunkParamUpdateForm(BaseModel):
    """Chunk param update form."""

    text_splitter: Optional[str] = None
    chunk_size: int
    chunk_overlap: int


class YoutubeLoaderConfig(BaseModel):
    """Youtube loader config form."""

    language: list[str]
    translation: Optional[str] = None
    proxy_url: str = ""


class WebSearchConfig(BaseModel):
    """Web search config form."""

    enabled: bool
    engine: Optional[str] = None
    searxng_query_url: Optional[str] = None
    google_pse_api_key: Optional[str] = None
    google_pse_engine_id: Optional[str] = None
    brave_search_api_key: Optional[str] = None
    kagi_search_api_key: Optional[str] = None
    mojeek_search_api_key: Optional[str] = None
    serpstack_api_key: Optional[str] = None
    serpstack_https: Optional[bool] = None
    serper_api_key: Optional[str] = None
    serply_api_key: Optional[str] = None
    tavily_api_key: Optional[str] = None
    searchapi_api_key: Optional[str] = None
    searchapi_engine: Optional[str] = None
    jina_api_key: Optional[str] = None
    bing_search_v7_endpoint: Optional[str] = None
    bing_search_v7_subscription_key: Optional[str] = None
    result_count: Optional[int] = None
    concurrent_requests: Optional[int] = None


class WebConfig(BaseModel):
    """Web config form."""

    search: WebSearchConfig
    web_loader_ssl_verification: Optional[bool] = None


class ConfigUpdateForm(BaseModel):
    """Config update form."""

    pdf_extract_images: Optional[bool] = None
    enable_google_drive_integration: Optional[bool] = None
    file: Optional[FileConfig] = None
    content_extraction: Optional[ContentExtractionConfig] = None
    chunk: Optional[ChunkParamUpdateForm] = None
    youtube: Optional[YoutubeLoaderConfig] = None
    web: Optional[WebConfig] = None


@router.post("/config/update")
async def update_rag_config(
    request: Request,
    form_data: ConfigUpdateForm,
    session: SessionDep,
    config_db: ConfigDBDep,
    user=Depends(get_admin_user),
):
    """Update RAG config."""
    config = config_db.data
    request.app.state.config.PDF_EXTRACT_IMAGES = (
        form_data.pdf_extract_images
        if form_data.pdf_extract_images is not None
        else request.app.state.config.PDF_EXTRACT_IMAGES
    )

    request.app.state.config.ENABLE_GOOGLE_DRIVE_INTEGRATION = (
        form_data.enable_google_drive_integration
        if form_data.enable_google_drive_integration is not None
        else request.app.state.config.ENABLE_GOOGLE_DRIVE_INTEGRATION
    )

    if form_data.file is not None:
        request.app.state.config.FILE_MAX_SIZE = form_data.file.max_size
        request.app.state.config.FILE_MAX_COUNT = form_data.file.max_count

    if form_data.content_extraction is not None:
        logger.info(f"Updating text settings: {form_data.content_extraction}")
        request.app.state.config.CONTENT_EXTRACTION_ENGINE = (
            form_data.content_extraction.engine
        )
        request.app.state.config.TIKA_SERVER_URL = (
            form_data.content_extraction.tika_server_url
        )

    if form_data.chunk is not None:
        request.app.state.config.TEXT_SPLITTER = form_data.chunk.text_splitter
        config.rag.chunk_size = form_data.chunk.chunk_size
        request.app.state.config.CHUNK_OVERLAP = form_data.chunk.chunk_overlap

    if form_data.youtube is not None:
        request.app.state.config.YOUTUBE_LOADER_LANGUAGE = form_data.youtube.language
        request.app.state.config.YOUTUBE_LOADER_PROXY_URL = form_data.youtube.proxy_url
        request.app.state.YOUTUBE_LOADER_TRANSLATION = form_data.youtube.translation

    if form_data.web is not None:
        request.app.state.config.ENABLE_RAG_WEB_LOADER_SSL_VERIFICATION = (
            # Note: When UI "Bypass SSL verification for Websites"=True then ENABLE_RAG_WEB_LOADER_SSL_VERIFICATION=False
            form_data.web.web_loader_ssl_verification
        )

        request.app.state.config.ENABLE_RAG_WEB_SEARCH = form_data.web.search.enabled
        request.app.state.config.RAG_WEB_SEARCH_ENGINE = form_data.web.search.engine
        request.app.state.config.SEARXNG_QUERY_URL = (
            form_data.web.search.searxng_query_url
        )
        request.app.state.config.GOOGLE_PSE_API_KEY = (
            form_data.web.search.google_pse_api_key
        )
        request.app.state.config.GOOGLE_PSE_ENGINE_ID = (
            form_data.web.search.google_pse_engine_id
        )
        request.app.state.config.BRAVE_SEARCH_API_KEY = (
            form_data.web.search.brave_search_api_key
        )
        request.app.state.config.KAGI_SEARCH_API_KEY = (
            form_data.web.search.kagi_search_api_key
        )
        request.app.state.config.MOJEEK_SEARCH_API_KEY = (
            form_data.web.search.mojeek_search_api_key
        )
        request.app.state.config.SERPSTACK_API_KEY = (
            form_data.web.search.serpstack_api_key
        )
        request.app.state.config.SERPSTACK_HTTPS = form_data.web.search.serpstack_https
        request.app.state.config.SERPER_API_KEY = form_data.web.search.serper_api_key
        request.app.state.config.SERPLY_API_KEY = form_data.web.search.serply_api_key
        request.app.state.config.TAVILY_API_KEY = form_data.web.search.tavily_api_key
        request.app.state.config.SEARCHAPI_API_KEY = (
            form_data.web.search.searchapi_api_key
        )
        request.app.state.config.SEARCHAPI_ENGINE = (
            form_data.web.search.searchapi_engine
        )

        request.app.state.config.JINA_API_KEY = form_data.web.search.jina_api_key
        request.app.state.config.BING_SEARCH_V7_ENDPOINT = (
            form_data.web.search.bing_search_v7_endpoint
        )
        request.app.state.config.BING_SEARCH_V7_SUBSCRIPTION_KEY = (
            form_data.web.search.bing_search_v7_subscription_key
        )

        request.app.state.config.RAG_WEB_SEARCH_RESULT_COUNT = (
            form_data.web.search.result_count
        )
        request.app.state.config.RAG_WEB_SEARCH_CONCURRENT_REQUESTS = (
            form_data.web.search.concurrent_requests
        )

    session.add(config_db)
    await session.commit()
    await session.refresh(config_db)
    config = config_db.data
    return {
        "status": True,
        "pdf_extract_images": request.app.state.config.PDF_EXTRACT_IMAGES,
        "file": {
            "max_size": request.app.state.config.FILE_MAX_SIZE,
            "max_count": request.app.state.config.FILE_MAX_COUNT,
        },
        "content_extraction": {
            "engine": request.app.state.config.CONTENT_EXTRACTION_ENGINE,
            "tika_server_url": request.app.state.config.TIKA_SERVER_URL,
        },
        "chunk": {
            "text_splitter": request.app.state.config.TEXT_SPLITTER,
            "chunk_size": config.rag.chunk_size,
            "chunk_overlap": request.app.state.config.CHUNK_OVERLAP,
        },
        "youtube": {
            "language": request.app.state.config.YOUTUBE_LOADER_LANGUAGE,
            "proxy_url": request.app.state.config.YOUTUBE_LOADER_PROXY_URL,
            "translation": request.app.state.YOUTUBE_LOADER_TRANSLATION,
        },
        "web": {
            "web_loader_ssl_verification": request.app.state.config.ENABLE_RAG_WEB_LOADER_SSL_VERIFICATION,
            "search": {
                "enabled": request.app.state.config.ENABLE_RAG_WEB_SEARCH,
                "engine": request.app.state.config.RAG_WEB_SEARCH_ENGINE,
                "searxng_query_url": request.app.state.config.SEARXNG_QUERY_URL,
                "google_pse_api_key": request.app.state.config.GOOGLE_PSE_API_KEY,
                "google_pse_engine_id": request.app.state.config.GOOGLE_PSE_ENGINE_ID,
                "brave_search_api_key": request.app.state.config.BRAVE_SEARCH_API_KEY,
                "kagi_search_api_key": request.app.state.config.KAGI_SEARCH_API_KEY,
                "mojeek_search_api_key": request.app.state.config.MOJEEK_SEARCH_API_KEY,
                "serpstack_api_key": request.app.state.config.SERPSTACK_API_KEY,
                "serpstack_https": request.app.state.config.SERPSTACK_HTTPS,
                "serper_api_key": request.app.state.config.SERPER_API_KEY,
                "serply_api_key": request.app.state.config.SERPLY_API_KEY,
                "serachapi_api_key": request.app.state.config.SEARCHAPI_API_KEY,
                "searchapi_engine": request.app.state.config.SEARCHAPI_ENGINE,
                "tavily_api_key": request.app.state.config.TAVILY_API_KEY,
                "jina_api_key": request.app.state.config.JINA_API_KEY,
                "bing_search_v7_endpoint": request.app.state.config.BING_SEARCH_V7_ENDPOINT,
                "bing_search_v7_subscription_key": request.app.state.config.BING_SEARCH_V7_SUBSCRIPTION_KEY,
                "result_count": request.app.state.config.RAG_WEB_SEARCH_RESULT_COUNT,
                "concurrent_requests": request.app.state.config.RAG_WEB_SEARCH_CONCURRENT_REQUESTS,
            },
        },
    }


@router.get("/template")
async def get_rag_template(config: ConfigDep, user=Depends(get_verified_user)):
    """Get RAG template."""
    return {
        "status": True,
        "template": config.rag.template,
    }


@router.get("/query/settings")
async def get_query_settings(
    request: Request, config: ConfigDep, user=Depends(get_admin_user)
):
    """Get query settings."""
    return {
        "status": True,
        "template": config.rag.template,
        "k": request.app.state.config.TOP_K,
        "r": request.app.state.config.RELEVANCE_THRESHOLD,
        "hybrid": request.app.state.config.ENABLE_RAG_HYBRID_SEARCH,
    }


class QuerySettingsForm(BaseModel):
    """Query settings form."""

    k: int = 4
    r: float = 0.0
    template: str | None = None
    hybrid: bool = False


@router.post("/query/settings/update")
async def update_query_settings(
    request: Request,
    form_data: QuerySettingsForm,
    session: SessionDep,
    config_db: ConfigDBDep,
    user=Depends(get_admin_user),
):
    """Update query settings."""
    config = config_db.data
    config.rag.template = form_data.template or config.rag.template
    request.app.state.config.TOP_K = form_data.k
    request.app.state.config.RELEVANCE_THRESHOLD = form_data.r

    request.app.state.config.ENABLE_RAG_HYBRID_SEARCH = form_data.hybrid

    config_db.data = config
    session.add(config_db)
    await session.commit()
    await session.refresh(config_db)
    config = config_db.data
    return {
        "status": True,
        "template": config.rag.template,
        "k": request.app.state.config.TOP_K,
        "r": request.app.state.config.RELEVANCE_THRESHOLD,
        "hybrid": request.app.state.config.ENABLE_RAG_HYBRID_SEARCH,
    }


def save_docs_to_vector_db(
    request: Request,
    docs,
    collection_name,
    config: ConfigData,
    metadata: Optional[dict] = None,
    overwrite: bool = False,
    split: bool = True,
    add: bool = False,
) -> bool:
    """Save documents to the vector database."""

    def _get_docs_info(docs: list[Document]) -> str:
        docs_info = set()

        # Trying to select relevant metadata identifying the document.
        for doc in docs:
            metadata = getattr(doc, "metadata", {})
            doc_name = metadata.get("name", "")
            if not doc_name:
                doc_name = metadata.get("title", "")
            if not doc_name:
                doc_name = metadata.get("source", "")
            if doc_name:
                docs_info.add(doc_name)

        return ", ".join(docs_info)

    logger.info(
        f"save_docs_to_vector_db: document {_get_docs_info(docs)} {collection_name}"
    )

    # Check if entries with the same hash (metadata.hash) already exist
    if metadata and "hash" in metadata:
        result = VECTOR_DB_CLIENT.query(
            collection_name=collection_name,
            filter={"hash": metadata["hash"]},
        )

        if result is not None and result.ids is not None:
            existing_doc_ids = result.ids[0]
            if existing_doc_ids:
                logger.info(f"Document with hash {metadata['hash']} already exists")
                raise ValueError(ERROR_MESSAGES.DUPLICATE_CONTENT)

    if split:
        if request.app.state.config.TEXT_SPLITTER in ["", "character"]:
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=config.rag.chunk_size,
                chunk_overlap=request.app.state.config.CHUNK_OVERLAP,
                add_start_index=True,
            )
        elif request.app.state.config.TEXT_SPLITTER == "token":
            logger.info(
                f"Using token text splitter: {request.app.state.config.TIKTOKEN_ENCODING_NAME}"
            )

            tiktoken.get_encoding(str(request.app.state.config.TIKTOKEN_ENCODING_NAME))
            text_splitter = TokenTextSplitter(
                encoding_name=str(request.app.state.config.TIKTOKEN_ENCODING_NAME),
                chunk_size=config.rag.chunk_size,
                chunk_overlap=request.app.state.config.CHUNK_OVERLAP,
                add_start_index=True,
            )
        else:
            raise ValueError("Invalid text splitter")

        docs = text_splitter.split_documents(docs)

    if len(docs) == 0:
        raise ValueError(ERROR_MESSAGES.EMPTY_CONTENT)

    texts = [doc.page_content for doc in docs]
    metadatas = [
        {
            **doc.metadata,
            **(metadata if metadata else {}),
            "embedding_config": json.dumps(
                {
                    "engine": request.app.state.config.RAG_EMBEDDING_ENGINE,
                    "model": request.app.state.config.RAG_EMBEDDING_MODEL,
                }
            ),
        }
        for doc in docs
    ]

    # ChromaDB does not like datetime formats
    # for meta-data so convert them to string.
    for metadata in metadatas:
        for key, value in metadata.items():
            if isinstance(value, datetime):
                metadata[key] = str(value)

    try:
        if VECTOR_DB_CLIENT.has_collection(collection_name=collection_name):
            logger.info(f"collection {collection_name} already exists")

            if overwrite:
                VECTOR_DB_CLIENT.delete_collection(collection_name=collection_name)
                logger.info(f"deleting existing collection {collection_name}")
            elif add is False:
                logger.info(
                    f"collection {collection_name} already exists, overwrite is False and add is False"
                )
                return True

        logger.info(f"adding to collection {collection_name}")
        embedding_function = get_embedding_function(
            request.app.state.config.RAG_EMBEDDING_ENGINE,
            request.app.state.config.RAG_EMBEDDING_MODEL,
            request.app.state.ef,
            (
                request.app.state.config.RAG_OPENAI_API_BASE_URL
                if request.app.state.config.RAG_EMBEDDING_ENGINE == "openai"
                else request.app.state.config.RAG_OLLAMA_BASE_URL
            ),
            (
                request.app.state.config.RAG_OPENAI_API_KEY
                if request.app.state.config.RAG_EMBEDDING_ENGINE == "openai"
                else request.app.state.config.RAG_OLLAMA_API_KEY
            ),
            request.app.state.config.RAG_EMBEDDING_BATCH_SIZE,
        )
        assert embedding_function is not None, "Embedding function is None"

        embeddings = embedding_function([text.replace("\n", " ") for text in texts])
        assert embeddings is not None, "Embeddings is None"

        items = [
            VectorItem.model_validate(
                {
                    "id": str(uuid.uuid4()),
                    "text": text,
                    "vector": embeddings[idx],
                    "metadata": metadatas[idx],
                }
            )
            for idx, text in enumerate(texts)
        ]

        VECTOR_DB_CLIENT.insert(
            collection_name=collection_name,
            items=items,
        )

        return True
    except Exception as e:
        logger.exception(e)
        raise e


class ProcessFileForm(BaseModel):
    """Process file form."""

    file_id: str
    content: Optional[str] = None
    collection_name: Optional[str] = None


@router.post("/process/file")
async def process_file(
    request: Request,
    form_data: ProcessFileForm,
    session: SessionDep,
    config: ConfigDep,
    user=Depends(get_verified_user),
):
    """Process file and save the content to the database."""
    try:
        file = await session.get_one(FileModel, id)
        assert file is not None, "File not found"

        collection_name = form_data.collection_name

        if collection_name is None:
            collection_name = f"file-{file.id}"

        if form_data.content:
            # Update the content in the file
            # Usage: /files/{file_id}/data/content/update

            VECTOR_DB_CLIENT.delete_collection(collection_name=f"file-{file.id}")

            docs = [
                Document(
                    page_content=form_data.content.replace("<br/>", "\n"),
                    metadata={
                        **(file.meta or {}),
                        "name": file.filename,
                        "created_by": file.user_id,
                        "file_id": file.id,
                        "source": file.filename,
                    },
                )
            ]

            text_content = form_data.content
        elif form_data.collection_name:
            # Check if the file has already been processed and save the content
            # Usage: /knowledge/{id}/file/add, /knowledge/{id}/file/update

            result = VECTOR_DB_CLIENT.query(
                collection_name=f"file-{file.id}", filter={"file_id": file.id}
            )

            if (
                result is not None
                and result.ids is not None
                and len(result.ids[0]) > 0
                and result.documents is not None
                and result.metadatas is not None
            ):
                docs = [
                    Document(
                        page_content=result.documents[0][idx],
                        metadata=result.metadatas[0][idx],
                    )
                    for idx, id in enumerate(result.ids[0])
                ]
            else:
                docs = [
                    Document(
                        page_content=(file.data or {}).get("content", ""),
                        metadata={
                            **(file.meta or {}),
                            "name": file.filename,
                            "created_by": file.user_id,
                            "file_id": file.id,
                            "source": file.filename,
                        },
                    )
                ]

            text_content = (file.data or {}).get("content", "")
        else:
            # Process the file and save the content
            # Usage: /files/
            file_path = file.path
            if file_path:
                loader = Loader(
                    engine=request.app.state.config.CONTENT_EXTRACTION_ENGINE,
                    TIKA_SERVER_URL=request.app.state.config.TIKA_SERVER_URL,
                    PDF_EXTRACT_IMAGES=request.app.state.config.PDF_EXTRACT_IMAGES,
                )
                docs = loader.load(
                    file.filename,
                    (file.meta or {}).get("content_type", ""),  # type: ignore
                    file_path,
                )

                docs = [
                    Document(
                        page_content=doc.page_content,
                        metadata={
                            **doc.metadata,
                            "name": file.filename,
                            "created_by": file.user_id,
                            "file_id": file.id,
                            "source": file.filename,
                        },
                    )
                    for doc in docs
                ]
            else:
                docs = [
                    Document(
                        page_content=(file.data or {}).get("content", ""),
                        metadata={
                            **(file.meta or {}),
                            "name": file.filename,
                            "created_by": file.user_id,
                            "file_id": file.id,
                            "source": file.filename,
                        },
                    )
                ]
            text_content = " ".join([doc.page_content for doc in docs])

        logger.debug(f"text_content: {text_content}")
        file.hash = calculate_sha256_string(text_content)
        file.data = (file.data or {}) | {"content": text_content}
        session.add(file)
        await session.commit()

        try:
            result = save_docs_to_vector_db(
                request,
                docs=docs,
                collection_name=collection_name,
                config=config,
                metadata={
                    "file_id": file.id,
                    "name": file.filename,
                    "hash": hash,
                },
                add=(True if form_data.collection_name else False),
            )

            if result:
                file.meta = (file.meta or {}) | {"collection_name": collection_name}  # type: ignore

                return {
                    "status": True,
                    "collection_name": collection_name,
                    "filename": file.filename,
                    "content": text_content,
                }
        except Exception as e:
            raise e
    except Exception as e:
        logger.exception(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pandoc is not installed on the server. Please contact your administrator for assistance."
            if "No pandoc was found" in str(e)
            else str(e),
        )


class ProcessTextForm(BaseModel):
    """Process text form."""

    name: str
    content: str
    collection_name: Optional[str] = None


@router.post("/process/text")
def process_text(
    request: Request,
    form_data: ProcessTextForm,
    config: ConfigDep,
    user=Depends(get_verified_user),
):
    """Process text and save the content to the database."""
    collection_name = form_data.collection_name or calculate_sha256_string(
        form_data.content
    )

    docs = [
        Document(
            page_content=form_data.content,
            metadata={"name": form_data.name, "created_by": user.id},
        )
    ]
    text_content = form_data.content
    logger.debug(f"text_content: {text_content}")

    if save_docs_to_vector_db(request, docs, collection_name, config):
        return {
            "status": True,
            "collection_name": collection_name,
            "content": text_content,
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error saving document to database",
        )


@router.post("/process/youtube")
def process_youtube_video(
    request: Request,
    form_data: ProcessUrlForm,
    config: ConfigDep,
    user=Depends(get_verified_user),
):
    """Process a YouTube video URL and save the content to the database."""
    try:
        collection_name = form_data.collection_name
        if not collection_name:
            collection_name = calculate_sha256_string(form_data.url)[:63]

        loader = YoutubeLoader(
            form_data.url,
            language=request.app.state.config.YOUTUBE_LOADER_LANGUAGE,
            proxy_url=request.app.state.config.YOUTUBE_LOADER_PROXY_URL,
        )

        docs = loader.load()
        content = " ".join([doc.page_content for doc in docs])
        logger.debug(f"text_content: {content}")

        save_docs_to_vector_db(request, docs, collection_name, config, overwrite=True)

        return {
            "status": True,
            "collection_name": collection_name,
            "filename": form_data.url,
            "file": {
                "data": {
                    "content": content,
                },
                "meta": {
                    "name": form_data.url,
                },
            },
        }
    except Exception as e:
        logger.exception(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/process/web")
def process_web(
    request: Request,
    form_data: ProcessUrlForm,
    config: ConfigDep,
    user=Depends(get_verified_user),
):
    """Process a web URL and save the content to the database."""
    try:
        collection_name = form_data.collection_name
        if not collection_name:
            collection_name = calculate_sha256_string(form_data.url)[:63]

        loader = get_web_loader(
            form_data.url,
            verify_ssl=request.app.state.config.ENABLE_RAG_WEB_LOADER_SSL_VERIFICATION,
            requests_per_second=request.app.state.config.RAG_WEB_SEARCH_CONCURRENT_REQUESTS,
        )
        docs = loader.load()
        content = " ".join([doc.page_content for doc in docs])

        logger.debug(f"text_content: {content}")
        save_docs_to_vector_db(request, docs, collection_name, config, overwrite=True)

        return {
            "status": True,
            "collection_name": collection_name,
            "filename": form_data.url,
            "file": {
                "data": {
                    "content": content,
                },
                "meta": {
                    "name": form_data.url,
                },
            },
        }
    except Exception as e:
        logger.exception(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


def search_web(
    request: Request, engine: str, query: str, config: ConfigData
) -> list[SearchResult]:
    """Search the web using a search engine and return the results as a list of SearchResult objects.

    Will look for a search engine API key in environment variables in the following order:
    - SEARXNG_QUERY_URL
    - GOOGLE_PSE_API_KEY + GOOGLE_PSE_ENGINE_ID
    - BRAVE_SEARCH_API_KEY
    - KAGI_SEARCH_API_KEY
    - MOJEEK_SEARCH_API_KEY
    - SERPSTACK_API_KEY
    - SERPER_API_KEY
    - SERPLY_API_KEY
    - TAVILY_API_KEY
    - SEARCHAPI_API_KEY + SEARCHAPI_ENGINE (by default `google`)

    Args:
        request (Request): The request object
        engine (str): The search engine to use
        query (str): The query to search for
        config (ConfigData): The configuration data

    """
    # TODO: add playwright to search the web
    if engine == "searxng":
        if request.app.state.config.SEARXNG_QUERY_URL:
            return search_searxng(
                request.app.state.config.SEARXNG_QUERY_URL,
                query,
                request.app.state.config.RAG_WEB_SEARCH_RESULT_COUNT,
                request.app.state.config.RAG_WEB_SEARCH_DOMAIN_FILTER_LIST,
            )
        else:
            raise Exception("No SEARXNG_QUERY_URL found in environment variables")
    elif engine == "google_pse":
        if (
            request.app.state.config.GOOGLE_PSE_API_KEY
            and request.app.state.config.GOOGLE_PSE_ENGINE_ID
        ):
            return search_google_pse(
                request.app.state.config.GOOGLE_PSE_API_KEY,
                request.app.state.config.GOOGLE_PSE_ENGINE_ID,
                query,
                request.app.state.config.RAG_WEB_SEARCH_RESULT_COUNT,
                request.app.state.config.RAG_WEB_SEARCH_DOMAIN_FILTER_LIST,
            )
        else:
            raise Exception(
                "No GOOGLE_PSE_API_KEY or GOOGLE_PSE_ENGINE_ID found in environment variables"
            )
    elif engine == "brave":
        if request.app.state.config.BRAVE_SEARCH_API_KEY:
            return search_brave(
                request.app.state.config.BRAVE_SEARCH_API_KEY,
                query,
                request.app.state.config.RAG_WEB_SEARCH_RESULT_COUNT,
                request.app.state.config.RAG_WEB_SEARCH_DOMAIN_FILTER_LIST,
            )
        else:
            raise Exception("No BRAVE_SEARCH_API_KEY found in environment variables")
    elif engine == "kagi":
        if request.app.state.config.KAGI_SEARCH_API_KEY:
            return search_kagi(
                request.app.state.config.KAGI_SEARCH_API_KEY,
                query,
                request.app.state.config.RAG_WEB_SEARCH_RESULT_COUNT,
                request.app.state.config.RAG_WEB_SEARCH_DOMAIN_FILTER_LIST,
            )
        else:
            raise Exception("No KAGI_SEARCH_API_KEY found in environment variables")
    elif engine == "mojeek":
        if request.app.state.config.MOJEEK_SEARCH_API_KEY:
            return search_mojeek(
                request.app.state.config.MOJEEK_SEARCH_API_KEY,
                query,
                request.app.state.config.RAG_WEB_SEARCH_RESULT_COUNT,
                request.app.state.config.RAG_WEB_SEARCH_DOMAIN_FILTER_LIST,
            )
        else:
            raise Exception("No MOJEEK_SEARCH_API_KEY found in environment variables")
    elif engine == "serpstack":
        if request.app.state.config.SERPSTACK_API_KEY:
            return search_serpstack(
                request.app.state.config.SERPSTACK_API_KEY,
                query,
                request.app.state.config.RAG_WEB_SEARCH_RESULT_COUNT,
                request.app.state.config.RAG_WEB_SEARCH_DOMAIN_FILTER_LIST,
                https_enabled=request.app.state.config.SERPSTACK_HTTPS,
            )
        else:
            raise Exception("No SERPSTACK_API_KEY found in environment variables")
    elif engine == "serper":
        if request.app.state.config.SERPER_API_KEY:
            return search_serper(
                request.app.state.config.SERPER_API_KEY,
                query,
                request.app.state.config.RAG_WEB_SEARCH_RESULT_COUNT,
                request.app.state.config.RAG_WEB_SEARCH_DOMAIN_FILTER_LIST,
            )
        else:
            raise Exception("No SERPER_API_KEY found in environment variables")
    elif engine == "serply":
        if request.app.state.config.SERPLY_API_KEY:
            return search_serply(
                request.app.state.config.SERPLY_API_KEY,
                query,
                request.app.state.config.RAG_WEB_SEARCH_RESULT_COUNT,
                request.app.state.config.RAG_WEB_SEARCH_DOMAIN_FILTER_LIST,
            )
        else:
            raise Exception("No SERPLY_API_KEY found in environment variables")
    elif engine == "duckduckgo":
        return search_duckduckgo(
            query,
            request.app.state.config.RAG_WEB_SEARCH_RESULT_COUNT,
            request.app.state.config.RAG_WEB_SEARCH_DOMAIN_FILTER_LIST,
        )
    elif engine == "tavily":
        if request.app.state.config.TAVILY_API_KEY:
            return search_tavily(
                request.app.state.config.TAVILY_API_KEY,
                query,
                request.app.state.config.RAG_WEB_SEARCH_RESULT_COUNT,
            )
        else:
            raise Exception("No TAVILY_API_KEY found in environment variables")
    elif engine == "searchapi":
        if request.app.state.config.SEARCHAPI_API_KEY:
            return search_searchapi(
                request.app.state.config.SEARCHAPI_API_KEY,
                request.app.state.config.SEARCHAPI_ENGINE,
                query,
                request.app.state.config.RAG_WEB_SEARCH_RESULT_COUNT,
                request.app.state.config.RAG_WEB_SEARCH_DOMAIN_FILTER_LIST,
            )
        else:
            raise Exception("No SEARCHAPI_API_KEY found in environment variables")
    elif engine == "jina":
        return search_jina(
            request.app.state.config.JINA_API_KEY,
            query,
            request.app.state.config.RAG_WEB_SEARCH_RESULT_COUNT,
        )
    elif engine == "bing":
        return search_bing(
            request.app.state.config.BING_SEARCH_V7_SUBSCRIPTION_KEY,
            request.app.state.config.BING_SEARCH_V7_ENDPOINT,
            config.ui.default_locale,
            query,
            request.app.state.config.RAG_WEB_SEARCH_RESULT_COUNT,
            request.app.state.config.RAG_WEB_SEARCH_DOMAIN_FILTER_LIST,
        )
    else:
        raise Exception("No search engine API key found in environment variables")


@router.post("/process/web/search")
def process_web_search(
    request: Request,
    form_data: SearchForm,
    config: ConfigDep,
    user=Depends(get_verified_user),
):
    """Process a web search query and save the results to the vector database."""
    try:
        logging.info(
            f"trying to web search with {request.app.state.config.RAG_WEB_SEARCH_ENGINE, form_data.query}"
        )
        web_results = search_web(
            request,
            request.app.state.config.RAG_WEB_SEARCH_ENGINE,
            form_data.query,
            config,
        )
    except Exception as e:
        logger.exception(e)

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    logger.debug(f"web_results: {web_results}")

    try:
        collection_name = form_data.collection_name
        if collection_name == "" or collection_name is None:
            collection_name = f"web-search-{calculate_sha256_string(form_data.query)}"[
                :63
            ]

        urls = [result.link for result in web_results]
        loader = get_web_loader(
            urls,
            verify_ssl=request.app.state.config.ENABLE_RAG_WEB_LOADER_SSL_VERIFICATION,
            requests_per_second=request.app.state.config.RAG_WEB_SEARCH_CONCURRENT_REQUESTS,
        )
        docs = loader.load()
        save_docs_to_vector_db(request, docs, collection_name, config, overwrite=True)

        return {
            "status": True,
            "collection_name": collection_name,
            "filenames": urls,
        }
    except Exception as e:
        logger.exception(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


class QueryDocForm(BaseModel):
    """Form model for querying a collection in the vector database."""

    collection_name: str
    query: str
    k: Optional[int] = None
    r: Optional[float] = None
    hybrid: Optional[bool] = None


@router.post("/query/doc")
def query_doc_handler(
    request: Request,
    form_data: QueryDocForm,
    user=Depends(get_verified_user),
):
    """Query a collection in the vector database."""
    try:
        if request.app.state.config.ENABLE_RAG_HYBRID_SEARCH:
            return query_doc_with_hybrid_search(
                collection_name=form_data.collection_name,
                query=form_data.query,
                embedding_function=request.app.state.EMBEDDING_FUNCTION,
                k=form_data.k if form_data.k else request.app.state.config.TOP_K,
                reranking_function=request.app.state.rf,
                r=(
                    form_data.r
                    if form_data.r
                    else request.app.state.config.RELEVANCE_THRESHOLD
                ),
            )
        else:
            return query_doc(
                collection_name=form_data.collection_name,
                query_embedding=request.app.state.EMBEDDING_FUNCTION(form_data.query),
                k=form_data.k if form_data.k else request.app.state.config.TOP_K,
            )
    except Exception as e:
        logger.exception(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


class QueryCollectionsForm(BaseModel):
    """Form model for querying collections in the vector database."""

    collection_names: list[str]
    query: str
    k: Optional[int] = None
    r: Optional[float] = None
    hybrid: Optional[bool] = None


@router.post("/query/collection")
def query_collection_handler(
    request: Request,
    form_data: QueryCollectionsForm,
    user=Depends(get_verified_user),
):
    """Query collections in the vector database."""
    try:
        if request.app.state.config.ENABLE_RAG_HYBRID_SEARCH:
            return query_collection_with_hybrid_search(
                collection_names=form_data.collection_names,
                queries=[form_data.query],
                embedding_function=request.app.state.EMBEDDING_FUNCTION,
                k=form_data.k if form_data.k else request.app.state.config.TOP_K,
                reranking_function=request.app.state.rf,
                r=(
                    form_data.r
                    if form_data.r
                    else request.app.state.config.RELEVANCE_THRESHOLD
                ),
            )
        else:
            return query_collection(
                collection_names=form_data.collection_names,
                queries=[form_data.query],
                embedding_function=request.app.state.EMBEDDING_FUNCTION,
                k=form_data.k if form_data.k else request.app.state.config.TOP_K,
            )

    except Exception as e:
        logger.exception(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


class DeleteForm(BaseModel):
    """Form model for deleting entries from a collection in the vector database."""

    collection_name: str
    file_id: str


@router.post("/delete")
async def delete_entries_from_collection(
    form_data: DeleteForm, session: SessionDep, user=Depends(get_admin_user)
):
    """Delete entries from a collection in the vector database."""
    try:
        if VECTOR_DB_CLIENT.has_collection(collection_name=form_data.collection_name):
            file = await session.get_one(FileModel, id)
            assert file is not None, "File not found"
            hash = file.hash

            VECTOR_DB_CLIENT.delete(
                collection_name=form_data.collection_name,
                filter={"hash": hash},
            )
            return {"status": True}
        else:
            return {"status": False}
    except Exception as e:
        logger.exception(e)
        return {"status": False}


@router.post("/reset/db")
def reset_vector_db(user=Depends(get_admin_user)):
    """Reset the vector database."""
    VECTOR_DB_CLIENT.reset()
    Knowledges.delete_all_knowledge()


@router.post("/reset/uploads")
def reset_upload_dir(user=Depends(get_admin_user)) -> bool:
    """Reset the upload directory."""
    folder = env.UPLOAD_DIR
    try:
        # Check if the directory exists
        if os.path.exists(folder):
            # Iterate over all the files and directories in the specified directory
            for filename in os.listdir(folder):
                file_path = os.path.join(folder, filename)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)  # Remove the file or link
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)  # Remove the directory
                except Exception as e:
                    logger.exception(f"Failed to delete {file_path}. Reason: {e}")
        else:
            logger.exception(f"The directory {folder} does not exist")
    except Exception as e:
        logger.exception(f"Failed to process the directory {folder}. Reason: {e}")
    return True


if env.WEBUI_ENV == "dev":

    @router.get("/ef/{text}")
    async def get_embeddings(request: Request, text: Optional[str] = "Hello World!"):
        """Get the embeddings for a given text."""
        return {"result": request.app.state.EMBEDDING_FUNCTION(text)}


class BatchProcessFilesForm(BaseModel):
    """Form model for batch processing files."""

    files: List[FileModel]
    collection_name: str


class BatchProcessFilesResult(BaseModel):
    """Result model for batch processing files."""

    file_id: str
    status: str
    error: Optional[str] = None


class BatchProcessFilesResponse(BaseModel):
    """Response model for batch processing files."""

    results: list[BatchProcessFilesResult]
    errors: list[BatchProcessFilesResult]


@router.post("/process/files/batch")
async def process_files_batch(
    request: Request,
    form_data: BatchProcessFilesForm,
    session: SessionDep,
    config: ConfigDep,
    user=Depends(get_verified_user),
) -> BatchProcessFilesResponse:
    """Process a batch of files and save them to the vector database."""
    results: list[BatchProcessFilesResult] = []
    errors: list[BatchProcessFilesResult] = []
    collection_name = form_data.collection_name

    # Prepare all documents first
    all_docs: list[Document] = []
    for file in form_data.files:
        try:
            text_content = (file.data or {}).get("content", "")

            docs: list[Document] = [
                Document(
                    page_content=text_content.replace("<br/>", "\n"),
                    metadata={
                        **(file.meta or {}),
                        "name": file.filename,
                        "created_by": file.user_id,
                        "file_id": file.id,
                        "source": file.filename,
                    },
                )
            ]

            file.hash = calculate_sha256_string(text_content)
            file.data = (file.data or {}) | {"content": text_content}
            session.add(file)
            await session.commit()

            all_docs.extend(docs)
            results.append(BatchProcessFilesResult(file_id=file.id, status="prepared"))

        except Exception as e:
            logger.error(
                f"process_files_batch: Error processing file {file.id}: {str(e)}"
            )
            errors.append(
                BatchProcessFilesResult(file_id=file.id, status="failed", error=str(e))
            )

    # Save all documents in one batch
    if all_docs:
        try:
            save_docs_to_vector_db(
                request=request,
                docs=all_docs,
                collection_name=collection_name,
                config=config,
                add=True,
            )

            # Update all files with collection name
            for result in results:
                file = await session.get_one(FileModel, result.file_id)
                file.meta = (file.meta or {}) | {"collection_name": collection_name}  # type: ignore
                result.status = "completed"

        except Exception as e:
            logger.error(
                f"process_files_batch: Error saving documents to vector DB: {str(e)}"
            )
            for result in results:
                result.status = "failed"
                errors.append(
                    BatchProcessFilesResult(
                        file_id=result.file_id, status="failed", error=str(e)
                    )
                )

    return BatchProcessFilesResponse(results=results, errors=errors)
