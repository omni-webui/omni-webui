import json
import mimetypes
import time
from contextlib import asynccontextmanager
from typing import Optional

import aiohttp
import requests
from art import text2art
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from pydantic import BaseModel, HttpUrl
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response, StreamingResponse

from omni_webui import __version__
from omni_webui.apps.audio.main import app as audio_app
from omni_webui.apps.images.main import app as images_app
from omni_webui.apps.ollama.main import app as ollama_app
from omni_webui.apps.ollama.main import get_all_models as get_ollama_models
from omni_webui.apps.openai.main import app as openai_app
from omni_webui.apps.openai.main import get_all_models as get_openai_models
from omni_webui.apps.rag.main import app as rag_app
from omni_webui.apps.rag.utils import rag_messages
from omni_webui.apps.socket.main import app as socket_app
from omni_webui.apps.webui.main import app as webui_app
from omni_webui.apps.webui.models.models import Models
from omni_webui.config import (
    CACHE_DIR,
    CHANGELOG,
    ModelFilter,
    config,
    settings,
)
from omni_webui.constants import ERROR_MESSAGES
from omni_webui.utils import (
    get_admin_user,
    get_current_user,
    get_http_authorization_cred,
    get_verified_user,
)


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
{text2art(settings.name)}

v{__version__} - building the best open-source AI user interface.
{f"Commit: {settings.build_hash}" if settings.build_hash != "dev-build" else ""}
https://github.com/omni-webui/omni-webui
"""
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    settings.database.close()


app = FastAPI(
    docs_url="/docs" if settings.env == "dev" else None,
    redoc_url=None,
    lifespan=lifespan,
)

app.state.MODELS = {}

origins = ["*"]


class RAGMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        return_citations = False

        if request.method == "POST" and (
            "/ollama/api/chat" in request.url.path
            or "/chat/completions" in request.url.path
        ):
            logger.debug(f"request.url.path: {request.url.path}")

            # Read the original request body
            body = await request.body()
            # Decode body to string
            body_str = body.decode("utf-8")
            # Parse string to JSON
            data = json.loads(body_str) if body_str else {}

            return_citations = data.get("citations", False)
            if "citations" in data:
                del data["citations"]

            # Example: Add a new key-value pair or modify existing ones
            # data["modified"] = True  # Example modification
            if "docs" in data:
                data = {**data}
                data["messages"], citations = rag_messages(
                    docs=data["docs"],
                    messages=data["messages"],
                    template=config.rag.template,
                    embedding_function=rag_app.state.EMBEDDING_FUNCTION,
                    k=config.rag.top_k,
                    reranking_function=rag_app.state.sentence_transformer_rf,
                    r=config.rag.relevance_threshold,
                    hybrid_search=config.rag.enable_hybrid_search,
                )
                del data["docs"]

                logger.debug(
                    f"data['messages']: {data['messages']}, citations: {citations}"
                )

            modified_body_bytes = json.dumps(data).encode("utf-8")

            # Replace the request body with the modified one
            request._body = modified_body_bytes

            # Set custom header to ensure content-length matches new body length
            request.headers.__dict__["_list"] = [
                (b"content-length", str(len(modified_body_bytes)).encode("utf-8")),
                *[
                    (k, v)
                    for k, v in request.headers.raw
                    if k.lower() != b"content-length"
                ],
            ]

        response = await call_next(request)

        if return_citations:
            # Inject the citations into the response
            if isinstance(response, StreamingResponse):
                # If it's a streaming response, inject it as SSE event or NDJSON line
                content_type = response.headers.get("Content-Type")
                if "text/event-stream" in content_type:
                    return StreamingResponse(
                        self.openai_stream_wrapper(response.body_iterator, citations),
                    )
                if "application/x-ndjson" in content_type:
                    return StreamingResponse(
                        self.ollama_stream_wrapper(response.body_iterator, citations),
                    )

        return response

    async def _receive(self, body: bytes):
        return {"type": "http.request", "body": body, "more_body": False}

    async def openai_stream_wrapper(self, original_generator, citations):
        yield f"data: {json.dumps({'citations': citations})}\n\n"
        async for data in original_generator:
            yield data

    async def ollama_stream_wrapper(self, original_generator, citations):
        yield f"{json.dumps({'citations': citations})}\n"
        async for data in original_generator:
            yield data


app.add_middleware(RAGMiddleware)


class PipelineMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "POST" and (
            "/ollama/api/chat" in request.url.path
            or "/chat/completions" in request.url.path
        ):
            logger.debug(f"request.url.path: {request.url.path}")

            # Read the original request body
            body = await request.body()
            # Decode body to string
            body_str = body.decode("utf-8")
            # Parse string to JSON
            data = json.loads(body_str) if body_str else {}

            model_id = data["model"]
            filters = [
                model
                for model in app.state.MODELS.values()
                if "pipeline" in model
                and "type" in model["pipeline"]
                and model["pipeline"]["type"] == "filter"
                and (
                    model["pipeline"]["pipelines"] == ["*"]
                    or any(
                        model_id == target_model_id
                        for target_model_id in model["pipeline"]["pipelines"]
                    )
                )
            ]
            sorted_filters = sorted(filters, key=lambda x: x["pipeline"]["priority"])

            user = None
            if len(sorted_filters) > 0:
                user = get_current_user(
                    get_http_authorization_cred(request.headers.get("Authorization"))
                )
                user = {"id": user.id, "name": user.name, "role": user.role}

            model = app.state.MODELS[model_id]

            if "pipeline" in model:
                sorted_filters.append(model)

            for filter in sorted_filters:
                r = None
                try:
                    urlIdx = filter["urlIdx"]

                    url = config.openai.base_urls[urlIdx]
                    key = config.openai.api_keys[urlIdx]

                    if key != "":
                        headers = {"Authorization": f"Bearer {key}"}
                        r = requests.post(
                            f"{url}/{filter['id']}/filter/inlet",
                            headers=headers,
                            json={
                                "user": user,
                                "body": data,
                            },
                        )

                        r.raise_for_status()
                        data = r.json()
                except Exception as e:
                    # Handle connection error here
                    print(f"Connection error: {e}")

                    if r is not None:
                        res = r.json()
                        if "detail" in res:
                            return JSONResponse(
                                status_code=r.status_code,
                                content=res,
                            )
                    else:
                        pass

            if "pipeline" not in app.state.MODELS[model_id]:
                if "chat_id" in data:
                    del data["chat_id"]

                if "title" in data:
                    del data["title"]

            modified_body_bytes = json.dumps(data).encode("utf-8")
            # Replace the request body with the modified one
            request._body = modified_body_bytes
            # Set custom header to ensure content-length matches new body length
            request.headers.__dict__["_list"] = [
                (b"content-length", str(len(modified_body_bytes)).encode("utf-8")),
                *[
                    (k, v)
                    for k, v in request.headers.raw
                    if k.lower() != b"content-length"
                ],
            ]

        response = await call_next(request)
        return response

    async def _receive(self, body: bytes):
        return {"type": "http.request", "body": body, "more_body": False}


app.add_middleware(PipelineMiddleware)


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def check_url(request: Request, call_next):
    if len(app.state.MODELS) == 0:
        await get_all_models()
    else:
        pass

    start_time = int(time.time())
    response = await call_next(request)
    process_time = int(time.time()) - start_time
    response.headers["X-Process-Time"] = str(process_time)

    return response


@app.middleware("http")
async def update_embedding_function(request: Request, call_next):
    response = await call_next(request)
    if "/embedding/update" in request.url.path:
        webui_app.state.EMBEDDING_FUNCTION = rag_app.state.EMBEDDING_FUNCTION
    return response


app.mount("/ws", socket_app)


app.mount("/ollama", ollama_app)
app.mount("/openai", openai_app)

app.mount("/images/api/v1", images_app)
app.mount("/audio/api/v1", audio_app)
app.mount("/rag/api/v1", rag_app)

app.mount("/api/v1", webui_app)

webui_app.state.EMBEDDING_FUNCTION = rag_app.state.EMBEDDING_FUNCTION


async def get_all_models():
    openai_models = []
    ollama_models = []

    if config.openai.enable:
        openai_models = await get_openai_models()

        openai_models = openai_models["data"]

    if config.ollama.enable:
        ollama_models = await get_ollama_models()

        ollama_models = [
            {
                "id": model["model"],
                "name": model["name"],
                "object": "model",
                "created": int(time.time()),
                "owned_by": "ollama",
                "ollama": model,
            }
            for model in ollama_models["models"]
        ]

    models = openai_models + ollama_models
    custom_models = Models.get_all_models()

    for custom_model in custom_models:
        if custom_model.base_model_id is None:
            for model in models:
                if (
                    custom_model.id == model["id"]
                    or custom_model.id == model["id"].split(":")[0]
                ):
                    model["name"] = custom_model.name
                    model["info"] = custom_model.model_dump()
        else:
            owned_by = "openai"
            for model in models:
                if (
                    custom_model.base_model_id == model["id"]
                    or custom_model.base_model_id == model["id"].split(":")[0]
                ):
                    owned_by = model["owned_by"]
                    break

            models.append(
                {
                    "id": custom_model.id,
                    "name": custom_model.name,
                    "object": "model",
                    "created": custom_model.created_at,
                    "owned_by": owned_by,
                    "info": custom_model.model_dump(),
                    "preset": True,
                }
            )

    app.state.MODELS = {model["id"]: model for model in models}

    webui_app.state.MODELS = app.state.MODELS

    return models


@app.get("/api/models")
async def get_models(user=Depends(get_verified_user)):
    models = await get_all_models()

    # Filter out filter pipelines
    models = [
        model
        for model in models
        if "pipeline" not in model or model["pipeline"].get("type", None) != "filter"
    ]

    if config.model_filter.enabled:
        if user.role == "user":
            models = list(
                filter(
                    lambda model: model["id"] in config.model_filter.models,
                    models,
                )
            )
            return {"data": models}

    return {"data": models}


@app.post("/api/chat/completed")
async def chat_completed(form_data: dict, user=Depends(get_verified_user)):
    data = form_data
    model_id = data["model"]

    filters = [
        model
        for model in app.state.MODELS.values()
        if "pipeline" in model
        and "type" in model["pipeline"]
        and model["pipeline"]["type"] == "filter"
        and (
            model["pipeline"]["pipelines"] == ["*"]
            or any(
                model_id == target_model_id
                for target_model_id in model["pipeline"]["pipelines"]
            )
        )
    ]
    sorted_filters = sorted(filters, key=lambda x: x["pipeline"]["priority"])

    print(model_id)

    if model_id in app.state.MODELS:
        model = app.state.MODELS[model_id]
        if "pipeline" in model:
            sorted_filters = [model] + sorted_filters

    for filter in sorted_filters:
        r = None
        try:
            urlIdx = filter["urlIdx"]

            url = config.openai.base_urls[urlIdx]
            key = config.openai.api_keys[urlIdx]

            if key != "":
                headers = {"Authorization": f"Bearer {key}"}
                r = requests.post(
                    f"{url}/{filter['id']}/filter/outlet",
                    headers=headers,
                    json={
                        "user": {"id": user.id, "name": user.name, "role": user.role},
                        "body": data,
                    },
                )

                r.raise_for_status()
                data = r.json()
        except Exception as e:
            # Handle connection error here
            print(f"Connection error: {e}")

            if r is not None:
                res = r.json()
                if "detail" in res:
                    return JSONResponse(
                        status_code=r.status_code,
                        content=res,
                    )
            else:
                pass

    return data


@app.get("/api/pipelines/list")
async def get_pipelines_list(user=Depends(get_admin_user)):
    responses = await get_openai_models(raw=True)

    logger.info(responses)
    urlIdxs = [
        idx
        for idx, response in enumerate(responses)
        if response is not None and "pipelines" in response
    ]

    return {
        "data": [
            {
                "url": config.openai.base_urls[urlIdx],
                "idx": urlIdx,
            }
            for urlIdx in urlIdxs
        ]
    }


class AddPipelineForm(BaseModel):
    url: str
    urlIdx: int


@app.post("/api/pipelines/add")
async def add_pipeline(form_data: AddPipelineForm, user=Depends(get_admin_user)):
    r = None
    try:
        urlIdx = form_data.urlIdx

        url = config.openai.base_urls[urlIdx]
        key = config.openai.api_keys[urlIdx]

        headers = {"Authorization": f"Bearer {key}"}
        r = requests.post(
            f"{url}/pipelines/add", headers=headers, json={"url": form_data.url}
        )

        r.raise_for_status()
        data = r.json()

        return {**data}
    except Exception as e:
        # Handle connection error here
        print(f"Connection error: {e}")

        detail = "Pipeline not found"
        if r is not None:
            res = r.json()
            if "detail" in res:
                detail = res["detail"]

        raise HTTPException(
            status_code=(r.status_code if r is not None else status.HTTP_404_NOT_FOUND),
            detail=detail,
        )


class DeletePipelineForm(BaseModel):
    id: str
    urlIdx: int


@app.delete("/api/pipelines/delete")
async def delete_pipeline(form_data: DeletePipelineForm, user=Depends(get_admin_user)):
    r = None
    try:
        urlIdx = form_data.urlIdx

        url = config.openai.base_urls[urlIdx]
        key = config.openai.api_keys[urlIdx]

        headers = {"Authorization": f"Bearer {key}"}
        r = requests.delete(
            f"{url}/pipelines/delete", headers=headers, json={"id": form_data.id}
        )

        r.raise_for_status()
        data = r.json()

        return {**data}
    except Exception as e:
        # Handle connection error here
        print(f"Connection error: {e}")

        detail = "Pipeline not found"
        if r is not None:
            res = r.json()
            if "detail" in res:
                detail = res["detail"]

        raise HTTPException(
            status_code=(r.status_code if r is not None else status.HTTP_404_NOT_FOUND),
            detail=detail,
        )


@app.get("/api/pipelines")
async def get_pipelines(urlIdx: Optional[int] = None, user=Depends(get_admin_user)):
    r = None
    try:
        assert urlIdx is not None

        url = config.openai.base_urls[urlIdx]
        key = config.openai.api_keys[urlIdx]

        headers = {"Authorization": f"Bearer {key}"}
        r = requests.get(f"{url}/pipelines", headers=headers)

        r.raise_for_status()
        data = r.json()

        return {**data}
    except Exception as e:
        # Handle connection error here
        print(f"Connection error: {e}")

        detail = "Pipeline not found"
        if r is not None:
            res = r.json()
            if "detail" in res:
                detail = res["detail"]

        raise HTTPException(
            status_code=(r.status_code if r is not None else status.HTTP_404_NOT_FOUND),
            detail=detail,
        )


@app.get("/api/pipelines/{pipeline_id}/valves")
async def get_pipeline_valves(
    urlIdx: Optional[int], pipeline_id: str, user=Depends(get_admin_user)
):
    await get_all_models()
    r = None
    try:
        assert urlIdx is not None
        url = config.openai.base_urls[urlIdx]
        key = config.openai.api_keys[urlIdx]

        headers = {"Authorization": f"Bearer {key}"}
        r = requests.get(f"{url}/{pipeline_id}/valves", headers=headers)

        r.raise_for_status()
        data = r.json()

        return {**data}
    except Exception as e:
        # Handle connection error here
        print(f"Connection error: {e}")

        detail = "Pipeline not found"

        if r is not None:
            res = r.json()
            if "detail" in res:
                detail = res["detail"]

        raise HTTPException(
            status_code=(r.status_code if r is not None else status.HTTP_404_NOT_FOUND),
            detail=detail,
        )


@app.get("/api/pipelines/{pipeline_id}/valves/spec")
async def get_pipeline_valves_spec(
    urlIdx: Optional[int], pipeline_id: str, user=Depends(get_admin_user)
):
    await get_all_models()

    r = None
    try:
        assert urlIdx is not None
        url = config.openai.base_urls[urlIdx]
        key = config.openai.api_keys[urlIdx]

        headers = {"Authorization": f"Bearer {key}"}
        r = requests.get(f"{url}/{pipeline_id}/valves/spec", headers=headers)

        r.raise_for_status()
        data = r.json()

        return {**data}
    except Exception as e:
        # Handle connection error here
        print(f"Connection error: {e}")

        detail = "Pipeline not found"
        if r is not None:
            res = r.json()
            if "detail" in res:
                detail = res["detail"]

        raise HTTPException(
            status_code=(r.status_code if r is not None else status.HTTP_404_NOT_FOUND),
            detail=detail,
        )


@app.post("/api/pipelines/{pipeline_id}/valves/update")
async def update_pipeline_valves(
    urlIdx: Optional[int],
    pipeline_id: str,
    form_data: dict,
    user=Depends(get_admin_user),
):
    await get_all_models()

    r = None
    try:
        assert urlIdx is not None
        url = config.openai.base_urls[urlIdx]
        key = config.openai.api_keys[urlIdx]

        headers = {"Authorization": f"Bearer {key}"}
        r = requests.post(
            f"{url}/{pipeline_id}/valves/update",
            headers=headers,
            json={**form_data},
        )

        r.raise_for_status()
        data = r.json()

        return {**data}
    except Exception as e:
        # Handle connection error here
        print(f"Connection error: {e}")

        detail = "Pipeline not found"

        if r is not None:
            res = r.json()
            if "detail" in res:
                detail = res["detail"]

        raise HTTPException(
            status_code=(r.status_code if r is not None else status.HTTP_404_NOT_FOUND),
            detail=detail,
        )


@app.get("/api/config")
async def get_app_config():
    # The Rest of the Function Now Uses the Variables Defined Above
    return {
        "status": True,
        "name": settings.name,
        "version": __version__,
        "default_locale": config.ui.default_locale,
        "default_models": config.ui.default_models,
        "default_prompt_suggestions": webui_app.state.config.DEFAULT_PROMPT_SUGGESTIONS,
        "features": {
            "auth": settings.auth,
            "auth_trusted_header": bool(webui_app.state.AUTH_TRUSTED_EMAIL_HEADER),
            "enable_signup": config.ui.enable_signup,
            "enable_web_search": config.rag.web_search.enable,
            "enable_image_generation": images_app.state.config.ENABLED,
            "enable_community_sharing": config.ui.enable_community_sharing,
            "enable_admin_export": settings.enable_admin_export,
        },
    }


@app.get("/api/config/model/filter")
async def get_model_filter_config(user=Depends(get_admin_user)):
    return config.model_filter


@app.post("/api/config/model/filter")
async def update_model_filter_config(
    form_data: ModelFilter, user=Depends(get_admin_user)
):
    config.model_filter.enabled = form_data.enabled
    config.model_filter.models = form_data.models

    return config.model_filter


@app.get("/api/webhook")
async def get_webhook_url(user=Depends(get_admin_user)):
    return {"url": config.webhook_url}


class UrlForm(BaseModel):
    url: HttpUrl


@app.post("/api/webhook")
async def update_webhook_url(form_data: UrlForm, user=Depends(get_admin_user)):
    config.webhook_url = str(form_data.url)
    return {"url": config.webhook_url}


@app.get("/api/version")
async def get_app_version():
    return {"version": __version__}


@app.get("/api/changelog")
async def get_app_changelog():
    return {key: value for i, (key, value) in enumerate(CHANGELOG.items()) if i < 5}


@app.get("/api/version/updates")
async def get_app_latest_release_version():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.github.com/repos/omni-webui/omni-webui/releases/latest"
            ) as response:
                response.raise_for_status()
                data = await response.json()
                latest_version = data["tag_name"]

                return {"current": __version__, "latest": latest_version[1:]}
    except aiohttp.ClientError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ERROR_MESSAGES.RATE_LIMIT_EXCEEDED,
        )


@app.get("/manifest.json")
async def get_manifest_json():
    return {
        "name": settings.name,
        "short_name": settings.name,
        "start_url": "/",
        "display": "standalone",
        "background_color": "#343541",
        "theme_color": "#343541",
        "orientation": "portrait-primary",
        "icons": [{"src": "/static/logo.png", "type": "image/png", "sizes": "500x500"}],
    }


@app.get("/opensearch.xml")
async def get_opensearch_xml():
    xml_content = rf"""
    <OpenSearchDescription xmlns="http://a9.com/-/spec/opensearch/1.1/" xmlns:moz="http://www.mozilla.org/2006/browser/search/">
    <ShortName>{settings.name}</ShortName>
    <Description>Search {settings.name}</Description>
    <InputEncoding>UTF-8</InputEncoding>
    <Image width="16" height="16" type="image/x-icon">{settings.url}/favicon.png</Image>
    <Url type="text/html" method="get" template="{settings.url}/?q={"{searchTerms}"}"/>
    <moz:SearchForm>{settings.url}</moz:SearchForm>
    </OpenSearchDescription>
    """
    return Response(content=xml_content, media_type="application/xml")


@app.get("/health")
async def healthcheck():
    return {"status": True}


app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")
app.mount("/cache", StaticFiles(directory=CACHE_DIR), name="cache")

if settings.frontend_build_dir.exists():
    mimetypes.add_type("text/javascript", ".js")
    app.mount(
        "/",
        SPAStaticFiles(directory=settings.frontend_build_dir, html=True),
        name="spa-static-files",
    )
else:
    logger.warning(
        f"Frontend build directory not found at '{settings.frontend_build_dir}'. Serving API only."
    )
