import json
import mimetypes
import os
import shutil
import socket
import urllib.parse
import uuid
from typing import List, Optional, Sequence, Union

import sentence_transformers
import validators
from chromadb.utils.batch_utils import create_batches
from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import (
    BSHTMLLoader,
    CSVLoader,
    Docx2txtLoader,
    PyPDFLoader,
    TextLoader,
    UnstructuredEPubLoader,
    UnstructuredExcelLoader,
    UnstructuredMarkdownLoader,
    UnstructuredPowerPointLoader,
    UnstructuredRSTLoader,
    UnstructuredXMLLoader,
    WebBaseLoader,
    YoutubeLoader,
)
from langchain_core.document_loaders import BaseLoader
from loguru import logger
from omni_webui.apps.rag.search.brave import search_brave
from omni_webui.apps.rag.search.google_pse import search_google_pse
from omni_webui.apps.rag.search.main import SearchResult
from omni_webui.apps.rag.search.searxng import search_searxng
from omni_webui.apps.rag.search.serper import search_serper
from omni_webui.apps.rag.search.serpstack import search_serpstack
from omni_webui.apps.rag.utils import (
    get_embedding_function,
    get_model_path,
    query_collection,
    query_collection_with_hybrid_search,
    query_doc,
    query_doc_with_hybrid_search,
)
from omni_webui.apps.webui.models.documents import (
    DocumentForm,
    Documents,
)
from omni_webui.config import (
    CHROMA_CLIENT,
    DEVICE_TYPE,
    RAG_EMBEDDING_MODEL_AUTO_UPDATE,
    RAG_EMBEDDING_MODEL_TRUST_REMOTE_CODE,
    RAG_RERANKING_MODEL_AUTO_UPDATE,
    RAG_RERANKING_MODEL_TRUST_REMOTE_CODE,
    UPLOAD_DIR,
    config,
    settings,
)
from omni_webui.constants import ERROR_MESSAGES
from omni_webui.utils import get_admin_user, get_current_user
from omni_webui.utils.misc import (
    calculate_sha256,
    calculate_sha256_string,
    extract_folders_after_data_docs,
    sanitize_filename,
)
from pydantic import BaseModel, HttpUrl

app = FastAPI()

app.state.YOUTUBE_LOADER_TRANSLATION = None


def update_embedding_model(
    embedding_model: str,
    update_model: bool = False,
):
    if embedding_model and config.rag.embedding_engine == "":
        app.state.sentence_transformer_ef = sentence_transformers.SentenceTransformer(
            get_model_path(embedding_model, update_model),
            device=DEVICE_TYPE,
            trust_remote_code=RAG_EMBEDDING_MODEL_TRUST_REMOTE_CODE,
        )
    else:
        app.state.sentence_transformer_ef = None


def update_reranking_model(
    reranking_model: str,
    update_model: bool = False,
):
    if reranking_model:
        app.state.sentence_transformer_rf = sentence_transformers.CrossEncoder(
            get_model_path(reranking_model, update_model),
            device=DEVICE_TYPE,
            trust_remote_code=RAG_RERANKING_MODEL_TRUST_REMOTE_CODE,
        )
    else:
        app.state.sentence_transformer_rf = None


update_embedding_model(
    config.rag.embedding_model,
    RAG_EMBEDDING_MODEL_AUTO_UPDATE,
)

update_reranking_model(
    config.rag.reranking_model,
    RAG_RERANKING_MODEL_AUTO_UPDATE,
)


app.state.EMBEDDING_FUNCTION = get_embedding_function(
    config.rag.embedding_engine,
    config.rag.embedding_model,
    app.state.sentence_transformer_ef,
    settings.openai_api_key,
    settings.openai_api_base_url,
    config.rag.embedding_openai_batch_size,
)

origins = ["*"]


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CollectionNameForm(BaseModel):
    collection_name: Optional[str] = "test"


class UrlForm(CollectionNameForm):
    url: str


class SearchForm(CollectionNameForm):
    query: str


@app.get("/")
async def get_status():
    return {
        "status": True,
        "chunk_size": config.rag.chunk_size,
        "chunk_overlap": config.rag.chunk_overlap,
        "template": config.rag.template,
        "embedding_engine": config.rag.embedding_engine,
        "embedding_model": config.rag.embedding_model,
        "reranking_model": config.rag.reranking_model,
        "openai_batch_size": config.rag.embedding_openai_batch_size,
    }


@app.get("/embedding")
async def get_embedding_config(user=Depends(get_admin_user)):
    return {
        "status": True,
        "embedding_engine": config.rag.embedding_engine,
        "embedding_model": config.rag.embedding_model,
        "openai_config": {
            "url": settings.openai_api_base_url,
            "key": settings.openai_api_key,
            "batch_size": config.rag.embedding_openai_batch_size,
        },
    }


@app.get("/reranking")
async def get_reraanking_config(user=Depends(get_admin_user)):
    return {
        "status": True,
        "reranking_model": config.rag.reranking_model,
    }


class OpenAIConfigForm(BaseModel):
    url: HttpUrl
    key: str
    batch_size: Optional[int] = None


class EmbeddingModelUpdateForm(BaseModel):
    openai_config: Optional[OpenAIConfigForm] = None
    embedding_engine: str
    embedding_model: str


@app.post("/embedding/update")
async def update_embedding_config(
    form_data: EmbeddingModelUpdateForm, user=Depends(get_admin_user)
):
    logger.info(
        f"Updating embedding model: {config.rag.embedding_model} to {form_data.embedding_model}"
    )
    try:
        config.rag.embedding_engine = form_data.embedding_engine
        config.rag.embedding_model = form_data.embedding_model

        if config.rag.embedding_engine in ["ollama", "openai"]:
            if form_data.openai_config is not None:
                settings.openai_api_base_url = form_data.openai_config.url
                settings.openai_api_key = form_data.openai_config.key
                config.rag.embedding_openai_batch_size = (
                    form_data.openai_config.batch_size
                    if form_data.openai_config.batch_size
                    else 1
                )

        update_embedding_model(config.rag.embedding_model)

        app.state.EMBEDDING_FUNCTION = get_embedding_function(
            config.rag.embedding_engine,
            config.rag.embedding_model,
            app.state.sentence_transformer_ef,
            settings.openai_api_key,
            settings.openai_api_base_url,
            config.rag.embedding_openai_batch_size,
        )

        return {
            "status": True,
            "embedding_engine": config.rag.embedding_engine,
            "embedding_model": config.rag.embedding_model,
            "openai_config": {
                "url": settings.openai_api_base_url,
                "key": settings.openai_api_key,
                "batch_size": config.rag.embedding_openai_batch_size,
            },
        }
    except Exception as e:
        logger.exception(f"Problem updating embedding model: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ERROR_MESSAGES.DEFAULT(e),
        )


class RerankingModelUpdateForm(BaseModel):
    reranking_model: str


@app.post("/reranking/update")
async def update_reranking_config(
    form_data: RerankingModelUpdateForm, user=Depends(get_admin_user)
):
    logger.info(
        f"Updating reranking model: {config.rag.reranking_model} to {form_data.reranking_model}"
    )
    try:
        config.rag.reranking_model = form_data.reranking_model

        update_reranking_model(config.rag.reranking_model), True

        return {
            "status": True,
            "reranking_model": config.rag.reranking_model,
        }
    except Exception as e:
        logger.exception(f"Problem updating reranking model: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ERROR_MESSAGES.DEFAULT(e),
        )


@app.get("/config")
async def get_rag_config(user=Depends(get_admin_user)):
    return {
        "status": True,
        "pdf_extract_images": config.rag.pdf_extract_images,
        "chunk": {
            "chunk_size": config.rag.chunk_size,
            "chunk_overlap": config.rag.chunk_overlap,
        },
        "youtube": {
            "language": config.rag.youtube_loader_language,
            "translation": app.state.YOUTUBE_LOADER_TRANSLATION,
        },
        "web": {
            "ssl_verification": config.rag.enable_web_loader_ssl_verification,
            "search": {
                "enabled": config.rag.web_search.enable,
                "engine": config.rag.web_search.engine,
                "searxng_query_url": config.rag.web_search.searxng_query_url,
                "google_pse_api_key": config.rag.web_search.google_pse_api_key,
                "google_pse_engine_id": config.rag.web_search.google_pse_engine_id,
                "brave_search_api_key": config.rag.web_search.brave_search_api_key,
                "serpstack_api_key": config.rag.web_search.serpstack_api_key,
                "serpstack_https": config.rag.web_search.serpstack_https,
                "serper_api_key": config.rag.web_search.serper_api_key,
                "result_count": config.rag.web_search.result_count,
                "concurrent_requests": config.rag.web_search.concurrent_requests,
            },
        },
    }


class ChunkParamUpdateForm(BaseModel):
    chunk_size: int
    chunk_overlap: int


class YoutubeLoaderConfig(BaseModel):
    language: List[str]
    translation: Optional[str] = None


class WebSearchConfig(BaseModel):
    enabled: bool
    engine: Optional[str] = None
    searxng_query_url: Optional[str] = None
    google_pse_api_key: Optional[str] = None
    google_pse_engine_id: Optional[str] = None
    brave_search_api_key: Optional[str] = None
    serpstack_api_key: Optional[str] = None
    serpstack_https: Optional[bool] = None
    serper_api_key: Optional[str] = None
    result_count: Optional[int] = None
    concurrent_requests: Optional[int] = None


class WebConfig(BaseModel):
    search: WebSearchConfig
    web_loader_ssl_verification: Optional[bool] = None


class ConfigUpdateForm(BaseModel):
    pdf_extract_images: Optional[bool] = None
    chunk: Optional[ChunkParamUpdateForm] = None
    youtube: Optional[YoutubeLoaderConfig] = None
    web: Optional[WebConfig] = None


@app.post("/config/update")
async def update_rag_config(form_data: ConfigUpdateForm, user=Depends(get_admin_user)):
    config.rag.pdf_extract_images = (
        form_data.pdf_extract_images
        if form_data.pdf_extract_images is not None
        else config.rag.pdf_extract_images
    )

    if form_data.chunk is not None:
        config.rag.chunk_size = form_data.chunk.chunk_size
        config.rag.chunk_overlap = form_data.chunk.chunk_overlap

    if form_data.youtube is not None:
        config.rag.youtube_loader_language = form_data.youtube.language
        app.state.YOUTUBE_LOADER_TRANSLATION = form_data.youtube.translation

    if form_data.web is not None:
        config.rag.enable_web_loader_ssl_verification = (
            form_data.web.web_loader_ssl_verification or False
        )

        config.rag.web_search.enable = form_data.web.search.enabled
        config.rag.web_search.engine = form_data.web.search.engine or ""
        config.rag.web_search.searxng_query_url = HttpUrl(
            form_data.web.search.searxng_query_url or "http://localhost:7700"
        )
        config.rag.web_search.google_pse_api_key = (
            form_data.web.search.google_pse_api_key or ""
        )
        config.rag.web_search.google_pse_engine_id = (
            form_data.web.search.google_pse_engine_id or ""
        )
        config.rag.web_search.brave_search_api_key = (
            form_data.web.search.brave_search_api_key or ""
        )
        config.rag.web_search.serpstack_api_key = (
            form_data.web.search.serpstack_api_key or ""
        )
        config.rag.web_search.serpstack_https = (
            form_data.web.search.serpstack_https or False
        )
        config.rag.web_search.serper_api_key = form_data.web.search.serper_api_key or ""
        config.rag.web_search.result_count = form_data.web.search.result_count or 3
        config.rag.web_search.concurrent_requests = (
            form_data.web.search.concurrent_requests or 10
        )

    return {
        "status": True,
        "pdf_extract_images": config.rag.pdf_extract_images,
        "chunk": {
            "chunk_size": config.rag.chunk_size,
            "chunk_overlap": config.rag.chunk_overlap,
        },
        "youtube": {
            "language": config.rag.youtube_loader_language,
            "translation": app.state.YOUTUBE_LOADER_TRANSLATION,
        },
        "web": {
            "ssl_verification": config.rag.enable_web_loader_ssl_verification,
            "search": {
                "enabled": config.rag.web_search.enable,
                "engine": config.rag.web_search.engine,
                "searxng_query_url": config.rag.web_search.searxng_query_url,
                "google_pse_api_key": config.rag.web_search.google_pse_api_key,
                "google_pse_engine_id": config.rag.web_search.google_pse_engine_id,
                "brave_search_api_key": config.rag.web_search.brave_search_api_key,
                "serpstack_api_key": config.rag.web_search.serpstack_api_key,
                "serpstack_https": config.rag.web_search.serpstack_https,
                "serper_api_key": config.rag.web_search.serper_api_key,
                "result_count": config.rag.web_search.result_count,
                "concurrent_requests": config.rag.web_search.concurrent_requests,
            },
        },
    }


@app.get("/template")
async def get_rag_template(user=Depends(get_current_user)):
    return {
        "status": True,
        "template": config.rag.template,
    }


@app.get("/query/settings")
async def get_query_settings(user=Depends(get_admin_user)):
    return {
        "status": True,
        "template": config.rag.template,
        "k": config.rag.top_k,
        "r": config.rag.relevance_threshold,
        "hybrid": config.rag.enable_hybrid_search,
    }


class QuerySettingsForm(BaseModel):
    k: Optional[int] = None
    r: Optional[float] = None
    template: Optional[str] = None
    hybrid: Optional[bool] = None


@app.post("/query/settings/update")
async def update_query_settings(
    form_data: QuerySettingsForm, user=Depends(get_admin_user)
):
    config.rag.template = form_data.template or config.rag.template
    config.rag.top_k = form_data.k if form_data.k else 4
    config.rag.relevance_threshold = form_data.r if form_data.r else 0.0
    config.rag.enable_hybrid_search = form_data.hybrid or False
    return {
        "status": True,
        "template": config.rag.template,
        "k": config.rag.top_k,
        "r": config.rag.relevance_threshold,
        "hybrid": config.rag.enable_hybrid_search,
    }


class QueryDocForm(BaseModel):
    collection_name: str
    query: str
    k: Optional[int] = None
    r: Optional[float] = None
    hybrid: Optional[bool] = None


@app.post("/query/doc")
def query_doc_handler(
    form_data: QueryDocForm,
    user=Depends(get_current_user),
):
    try:
        if config.rag.enable_hybrid_search:
            return query_doc_with_hybrid_search(
                collection_name=form_data.collection_name,
                query=form_data.query,
                embedding_function=app.state.EMBEDDING_FUNCTION,
                k=form_data.k or config.rag.top_k,
                reranking_function=app.state.sentence_transformer_rf,
                r=form_data.r or config.rag.relevance_threshold,
            )
        else:
            return query_doc(
                collection_name=form_data.collection_name,
                query=form_data.query,
                embedding_function=app.state.EMBEDDING_FUNCTION,
                k=form_data.k or config.rag.top_k,
            )
    except Exception as e:
        logger.exception(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(e),
        )


class QueryCollectionsForm(BaseModel):
    collection_names: List[str]
    query: str
    k: Optional[int] = None
    r: Optional[float] = None
    hybrid: Optional[bool] = None


@app.post("/query/collection")
def query_collection_handler(
    form_data: QueryCollectionsForm,
    user=Depends(get_current_user),
):
    try:
        if config.rag.enable_hybrid_search:
            return query_collection_with_hybrid_search(
                collection_names=form_data.collection_names,
                query=form_data.query,
                embedding_function=app.state.EMBEDDING_FUNCTION,
                k=form_data.k or config.rag.top_k,
                reranking_function=app.state.sentence_transformer_rf,
                r=form_data.r or config.rag.relevance_threshold,
            )
        else:
            return query_collection(
                collection_names=form_data.collection_names,
                query=form_data.query,
                embedding_function=app.state.EMBEDDING_FUNCTION,
                k=form_data.k or config.rag.top_k,
            )

    except Exception as e:
        logger.exception(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(e),
        )


@app.post("/youtube")
def store_youtube_video(form_data: UrlForm, user=Depends(get_current_user)):
    try:
        loader = YoutubeLoader.from_youtube_url(
            form_data.url,
            add_video_info=True,
            language=config.rag.youtube_loader_language,
            translation=app.state.YOUTUBE_LOADER_TRANSLATION,
        )
        data = loader.load()

        collection_name = form_data.collection_name
        if collection_name == "":
            collection_name = calculate_sha256_string(form_data.url)[:63]

        store_data_in_vector_db(data, collection_name, overwrite=True)
        return {
            "status": True,
            "collection_name": collection_name,
            "filename": form_data.url,
        }
    except Exception as e:
        logger.exception(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(e),
        )


@app.post("/web")
def store_web(form_data: UrlForm, user=Depends(get_current_user)):
    # "https://www.gutenberg.org/files/1727/1727-h/1727-h.htm"
    try:
        loader = get_web_loader(
            form_data.url,
            verify_ssl=config.rag.enable_web_loader_ssl_verification,
        )
        data = loader.load()

        collection_name = form_data.collection_name
        if collection_name == "":
            collection_name = calculate_sha256_string(form_data.url)[:63]

        store_data_in_vector_db(data, collection_name, overwrite=True)
        return {
            "status": True,
            "collection_name": collection_name,
            "filename": form_data.url,
        }
    except Exception as e:
        logger.exception(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(e),
        )


def get_web_loader(url: Union[str, Sequence[str]], verify_ssl: bool = True):
    # Check if the URL is valid
    if not validate_url(url):
        raise ValueError(ERROR_MESSAGES.INVALID_URL)
    return WebBaseLoader(
        url,
        verify_ssl=verify_ssl,
        requests_per_second=config.rag.web_search.concurrent_requests,
        continue_on_failure=True,
    )


def validate_url(url: Union[str, Sequence[str]]):
    if isinstance(url, str):
        if isinstance(validators.url(url), validators.ValidationError):
            raise ValueError(ERROR_MESSAGES.INVALID_URL)
        if not settings.enable_rag_local_web_fetch:
            # Local web fetch is disabled, filter out any URLs that resolve to private IP addresses
            parsed_url = urllib.parse.urlparse(url)
            # Get IPv4 and IPv6 addresses
            ipv4_addresses, ipv6_addresses = resolve_hostname(parsed_url.hostname)
            # Check if any of the resolved addresses are private
            # This is technically still vulnerable to DNS rebinding attacks, as we don't control WebBaseLoader
            for ip in ipv4_addresses:
                if validators.ipv4(ip, private=True):
                    raise ValueError(ERROR_MESSAGES.INVALID_URL)
            for ip in ipv6_addresses:
                if validators.ipv6(ip, private=True):
                    raise ValueError(ERROR_MESSAGES.INVALID_URL)
        return True
    elif isinstance(url, Sequence):
        return all(validate_url(u) for u in url)
    else:
        return False


def resolve_hostname(hostname):
    # Get address information
    addr_info = socket.getaddrinfo(hostname, None)

    # Extract IP addresses from address information
    ipv4_addresses = [info[4][0] for info in addr_info if info[0] == socket.AF_INET]
    ipv6_addresses = [info[4][0] for info in addr_info if info[0] == socket.AF_INET6]

    return ipv4_addresses, ipv6_addresses


def search_web(engine: str, query: str) -> list[SearchResult]:
    """Search the web using a search engine and return the results as a list of SearchResult objects.
    Will look for a search engine API key in environment variables in the following order:
    - SEARXNG_QUERY_URL
    - GOOGLE_PSE_API_KEY + GOOGLE_PSE_ENGINE_ID
    - BRAVE_SEARCH_API_KEY
    - SERPSTACK_API_KEY
    - SERPER_API_KEY

    Args:
        query (str): The query to search for
    """

    # TODO: add playwright to search the web
    if engine == "searxng":
        if config.rag.web_search.searxng_query_url:
            return search_searxng(
                str(config.rag.web_search.searxng_query_url),
                query,
                config.rag.web_search.result_count,
            )
        else:
            raise Exception("No SEARXNG_QUERY_URL found in environment variables")
    elif engine == "google_pse":
        if (
            config.rag.web_search.google_pse_api_key
            and config.rag.web_search.google_pse_engine_id
        ):
            return search_google_pse(
                config.rag.web_search.google_pse_api_key,
                config.rag.web_search.google_pse_engine_id,
                query,
                config.rag.web_search.result_count,
            )
        else:
            raise Exception(
                "No GOOGLE_PSE_API_KEY or GOOGLE_PSE_ENGINE_ID found in environment variables"
            )
    elif engine == "brave":
        if config.rag.web_search.brave_search_api_key:
            return search_brave(
                config.rag.web_search.brave_search_api_key,
                query,
                config.rag.web_search.result_count,
            )
        else:
            raise Exception("No BRAVE_SEARCH_API_KEY found in environment variables")
    elif engine == "serpstack":
        if config.rag.web_search.serpstack_api_key:
            return search_serpstack(
                config.rag.web_search.serpstack_api_key,
                query,
                config.rag.web_search.result_count,
                https_enabled=config.rag.web_search.serpstack_https,
            )
        else:
            raise Exception("No SERPSTACK_API_KEY found in environment variables")
    elif engine == "serper":
        if config.rag.web_search.serper_api_key:
            return search_serper(
                config.rag.web_search.serper_api_key,
                query,
                config.rag.web_search.result_count,
            )
        else:
            raise Exception("No SERPER_API_KEY found in environment variables")
    else:
        raise Exception("No search engine API key found in environment variables")


@app.post("/web/search")
def store_web_search(form_data: SearchForm, user=Depends(get_current_user)):
    try:
        web_results = search_web(config.rag.web_search.engine, form_data.query)
    except Exception as e:
        logger.exception(e)

        print(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.WEB_SEARCH_ERROR(e),
        )

    try:
        urls = [result.link for result in web_results]
        loader = get_web_loader(urls)
        data = loader.load()

        collection_name = form_data.collection_name
        if collection_name == "":
            collection_name = calculate_sha256_string(form_data.query)[:63]

        store_data_in_vector_db(data, collection_name, overwrite=True)
        return {
            "status": True,
            "collection_name": collection_name,
            "filenames": urls,
        }
    except Exception as e:
        logger.exception(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(e),
        )


def store_data_in_vector_db(data, collection_name, overwrite: bool = False) -> bool:
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.rag.chunk_size,
        chunk_overlap=config.rag.chunk_overlap,
        add_start_index=True,
    )

    docs = text_splitter.split_documents(data)

    if len(docs) > 0:
        logger.info(f"store_data_in_vector_db {docs}")
        return store_docs_in_vector_db(docs, collection_name, overwrite)
    else:
        raise ValueError(ERROR_MESSAGES.EMPTY_CONTENT)


def store_text_in_vector_db(
    text, metadata, collection_name, overwrite: bool = False
) -> bool:
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.rag.chunk_size,
        chunk_overlap=config.rag.chunk_overlap,
        add_start_index=True,
    )
    docs = text_splitter.create_documents([text], metadatas=[metadata])
    return store_docs_in_vector_db(docs, collection_name, overwrite)


def store_docs_in_vector_db(docs, collection_name, overwrite: bool = False) -> bool:
    logger.info(f"store_docs_in_vector_db {docs} {collection_name}")

    texts = [doc.page_content for doc in docs]
    metadatas = [doc.metadata for doc in docs]

    try:
        if overwrite:
            for collection in CHROMA_CLIENT.list_collections():
                if collection_name == collection.name:
                    logger.info(f"deleting existing collection {collection_name}")
                    CHROMA_CLIENT.delete_collection(name=collection_name)

        collection = CHROMA_CLIENT.create_collection(name=collection_name)

        embedding_func = get_embedding_function(
            config.rag.embedding_engine,
            config.rag.embedding_model,
            app.state.sentence_transformer_ef,
            settings.openai_api_key,
            settings.openai_api_base_url,
            config.rag.embedding_openai_batch_size,
        )

        embedding_texts = list(map(lambda x: x.replace("\n", " "), texts))
        embeddings = embedding_func(embedding_texts)

        for batch in create_batches(
            api=CHROMA_CLIENT,
            ids=[str(uuid.uuid4()) for _ in texts],
            metadatas=metadatas,
            embeddings=embeddings,
            documents=texts,
        ):
            collection.add(*batch)

        return True
    except Exception as e:
        logger.exception(e)
        if e.__class__.__name__ == "UniqueConstraintError":
            return True

        return False


def get_loader(filename: str, file_content_type: str, file_path: str):
    file_ext = filename.split(".")[-1].lower()
    known_type = True

    known_source_ext = [
        "go",
        "py",
        "java",
        "sh",
        "bat",
        "ps1",
        "cmd",
        "js",
        "ts",
        "css",
        "cpp",
        "hpp",
        "h",
        "c",
        "cs",
        "sql",
        "log",
        "ini",
        "pl",
        "pm",
        "r",
        "dart",
        "dockerfile",
        "env",
        "php",
        "hs",
        "hsc",
        "lua",
        "nginxconf",
        "conf",
        "m",
        "mm",
        "plsql",
        "perl",
        "rb",
        "rs",
        "db2",
        "scala",
        "bash",
        "swift",
        "vue",
        "svelte",
    ]

    loader: BaseLoader
    if file_ext == "pdf":
        loader = PyPDFLoader(file_path, extract_images=config.rag.pdf_extract_images)
    elif file_ext == "csv":
        loader = CSVLoader(file_path)
    elif file_ext == "rst":
        loader = UnstructuredRSTLoader(file_path, mode="elements")
    elif file_ext == "xml":
        loader = UnstructuredXMLLoader(file_path)
    elif file_ext in ["htm", "html"]:
        loader = BSHTMLLoader(file_path, open_encoding="unicode_escape")
    elif file_ext == "md":
        loader = UnstructuredMarkdownLoader(file_path)
    elif file_content_type == "application/epub+zip":
        loader = UnstructuredEPubLoader(file_path)
    elif (
        file_content_type
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        or file_ext in ["doc", "docx"]
    ):
        loader = Docx2txtLoader(file_path)
    elif file_content_type in [
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ] or file_ext in ["xls", "xlsx"]:
        loader = UnstructuredExcelLoader(file_path)
    elif file_content_type in [
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ] or file_ext in ["ppt", "pptx"]:
        loader = UnstructuredPowerPointLoader(file_path)
    elif file_ext in known_source_ext or (
        file_content_type and file_content_type.find("text/") >= 0
    ):
        loader = TextLoader(file_path, autodetect_encoding=True)
    else:
        loader = TextLoader(file_path, autodetect_encoding=True)
        known_type = False

    return loader, known_type


@app.post("/doc")
def store_doc(
    collection_name: Optional[str] = Form(None),
    file: UploadFile = File(...),
    user=Depends(get_current_user),
):
    # "https://www.gutenberg.org/files/1727/1727-h/1727-h.htm"

    logger.info(f"file.content_type: {file.content_type}")
    try:
        unsanitized_filename = file.filename
        filename = os.path.basename(unsanitized_filename)

        file_path = f"{UPLOAD_DIR}/{filename}"

        contents = file.file.read()
        with open(file_path, "wb") as f:
            f.write(contents)
            f.close()

        with open(file_path, "rb") as f:
            if collection_name is None:
                collection_name = calculate_sha256(f)[:63]

        loader, known_type = get_loader(filename, file.content_type, file_path)
        data = loader.load()

        try:
            result = store_data_in_vector_db(data, collection_name)

            if result:
                return {
                    "status": True,
                    "collection_name": collection_name,
                    "filename": filename,
                    "known_type": known_type,
                }
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=e,
            )
    except Exception as e:
        logger.exception(e)
        if "No pandoc was found" in str(e):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.PANDOC_NOT_INSTALLED,
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.DEFAULT(e),
            )


class TextRAGForm(BaseModel):
    name: str
    content: str
    collection_name: Optional[str] = None


@app.post("/text")
def store_text(
    form_data: TextRAGForm,
    user=Depends(get_current_user),
):
    collection_name = form_data.collection_name
    if collection_name is None:
        collection_name = calculate_sha256_string(form_data.content)

    result = store_text_in_vector_db(
        form_data.content,
        metadata={"name": form_data.name, "created_by": user.id},
        collection_name=collection_name,
    )

    if result:
        return {"status": True, "collection_name": collection_name}
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ERROR_MESSAGES.DEFAULT(),
        )


@app.get("/scan")
def scan_docs_dir(user=Depends(get_admin_user)):
    for path in settings.docs_dir.rglob("./**/*"):
        try:
            if path.is_file() and not path.name.startswith("."):
                tags = extract_folders_after_data_docs(path)
                filename = path.name
                file_content_type = mimetypes.guess_type(path)

                f = open(path, "rb")
                collection_name = calculate_sha256(f)[:63]
                f.close()

                loader, known_type = get_loader(
                    filename, file_content_type[0], str(path)
                )
                data = loader.load()

                try:
                    result = store_data_in_vector_db(data, collection_name)

                    if result:
                        sanitized_filename = sanitize_filename(filename)
                        doc = Documents.get_doc_by_name(sanitized_filename)

                        if doc is None:
                            doc = Documents.insert_new_doc(
                                user.id,
                                DocumentForm(
                                    **{
                                        "name": sanitized_filename,
                                        "title": filename,
                                        "collection_name": collection_name,
                                        "filename": filename,
                                        "content": (
                                            json.dumps(
                                                {
                                                    "tags": list(
                                                        map(
                                                            lambda name: {"name": name},
                                                            tags,
                                                        )
                                                    )
                                                }
                                            )
                                            if len(tags)
                                            else "{}"
                                        ),
                                    }
                                ),
                            )
                except Exception as e:
                    logger.exception(e)
                    pass

        except Exception as e:
            logger.exception(e)

    return True


@app.get("/reset/db")
def reset_vector_db(user=Depends(get_admin_user)):
    CHROMA_CLIENT.reset()


@app.get("/reset/uploads")
def reset_upload_dir(user=Depends(get_admin_user)) -> bool:
    folder = f"{UPLOAD_DIR}"
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
                    print(f"Failed to delete {file_path}. Reason: {e}")
        else:
            print(f"The directory {folder} does not exist")
    except Exception as e:
        print(f"Failed to process the directory {folder}. Reason: {e}")

    return True


@app.get("/reset")
def reset(user=Depends(get_admin_user)) -> bool:
    for path in UPLOAD_DIR.iterdir():
        try:
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                shutil.rmtree(path)
        except Exception as e:
            logger.error(f"Failed to delete {path}. Reason: {e}")
    try:
        CHROMA_CLIENT.reset()
    except Exception as e:
        logger.exception(e)

    return True


if settings.env == "dev":

    @app.get("/ef")
    async def get_embeddings():
        return {"result": app.state.EMBEDDING_FUNCTION("hello world")}

    @app.get("/ef/{text}")
    async def get_embeddings_text(text: str):
        return {"result": app.state.EMBEDDING_FUNCTION(text)}
