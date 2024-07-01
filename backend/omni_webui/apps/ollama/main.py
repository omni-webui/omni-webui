import asyncio
import json
import os
import random
import re
import time
from typing import List, Optional, Union
from urllib.parse import urlparse

import aiohttp
import requests
from fastapi import (
    Depends,
    FastAPI,
    File,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from loguru import logger
from omni_webui.apps.webui.models.models import Models
from omni_webui.config import (
    UPLOAD_DIR,
    config,
)
from omni_webui.constants import ERROR_MESSAGES
from omni_webui.utils import (
    get_admin_user,
    get_verified_user,
)
from omni_webui.utils.misc import calculate_sha256
from pydantic import BaseModel, ConfigDict, HttpUrl
from starlette.background import BackgroundTask

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.config = config
app.state.MODELS = {}


# TODO: Implement a more intelligent load balancing mechanism for distributing requests among multiple backend instances.
# Current implementation uses a simple round-robin approach (random.choice). Consider incorporating algorithms like weighted round-robin,
# least connections, or least response time for better resource utilization and performance optimization.


@app.middleware("http")
async def check_url(request: Request, call_next):
    if len(app.state.MODELS) == 0:
        await get_all_models()
    else:
        pass

    response = await call_next(request)
    return response


@app.head("/")
@app.get("/")
async def get_status():
    return {"status": True}


@app.get("/config")
async def get_config(user=Depends(get_admin_user)):
    return {"ENABLE_OLLAMA_API": app.state.config.ENABLE_OLLAMA_API}


class OllamaConfigForm(BaseModel):
    enable_ollama_api: Optional[bool] = None


@app.post("/config/update")
async def update_config(form_data: OllamaConfigForm, user=Depends(get_admin_user)):
    app.state.config.ENABLE_OLLAMA_API = form_data.enable_ollama_api
    return {"ENABLE_OLLAMA_API": app.state.config.ENABLE_OLLAMA_API}


@app.get("/urls")
async def get_ollama_api_urls(user=Depends(get_admin_user)):
    return {"OLLAMA_BASE_URLS": config.ollama.base_urls}


class UrlUpdateForm(BaseModel):
    urls: List[str]


@app.post("/urls/update")
async def update_ollama_api_url(form_data: UrlUpdateForm, user=Depends(get_admin_user)):
    config.ollama.base_urls = [HttpUrl(url) for url in form_data.urls]

    logger.info(f"{config.ollama.base_urls = }")
    return {"OLLAMA_BASE_URLS": config.ollama.base_urls}


async def fetch_url(url):
    timeout = aiohttp.ClientTimeout(total=5)
    try:
        async with aiohttp.ClientSession(timeout=timeout, trust_env=True) as session:
            async with session.get(url) as response:
                return await response.json()
    except Exception as e:
        # Handle connection error here
        logger.error(f"Connection error: {e}")
        return None


async def cleanup_response(
    response: Optional[aiohttp.ClientResponse],
    session: Optional[aiohttp.ClientSession],
):
    if response:
        response.close()
    if session:
        await session.close()


async def post_streaming_url(url: str, payload: bytes):
    r = None
    try:
        session = aiohttp.ClientSession(trust_env=True)
        r = await session.post(url, data=payload)
        r.raise_for_status()

        return StreamingResponse(
            r.content,
            status_code=r.status,
            headers=dict(r.headers),
            background=BackgroundTask(cleanup_response, response=r, session=session),
        )
    except Exception as e:
        error_detail = "Omni WebUI: Server Connection Error"
        if r is not None:
            try:
                res = await r.json()
                if "error" in res:
                    error_detail = f"Ollama: {res['error']}"
            except (json.JSONDecodeError, aiohttp.ContentTypeError):
                error_detail = f"Ollama: {e}"

        raise HTTPException(
            status_code=r.status if r else 500,
            detail=error_detail,
        )


def merge_models_lists(model_lists):
    merged_models = {}

    for idx, model_list in enumerate(model_lists):
        if model_list is not None:
            for model in model_list:
                digest = model["digest"]
                if digest not in merged_models:
                    model["urls"] = [idx]
                    merged_models[digest] = model
                else:
                    merged_models[digest]["urls"].append(idx)

    return list(merged_models.values())


# user=Depends(get_current_user)


async def get_all_models():
    logger.info("get_all_models()")

    if app.state.config.ENABLE_OLLAMA_API:
        tasks = [fetch_url(f"{url}/api/tags") for url in config.ollama.base_urls]
        responses = await asyncio.gather(*tasks)

        models = {
            "models": merge_models_lists(
                map(
                    lambda response: response["models"] if response else None, responses
                )
            )
        }

    else:
        models = {"models": []}

    app.state.MODELS = {model["model"]: model for model in models["models"]}

    return models


@app.get("/api/tags")
@app.get("/api/tags/{url_idx}")
async def get_ollama_tags(
    url_idx: Optional[int] = None, user=Depends(get_verified_user)
):
    if url_idx is None:
        models = await get_all_models()

        if config.model_filter.enabled:
            if user.role == "user":
                models["models"] = list(
                    filter(
                        lambda model: model["name"] in config.model_filter.models,
                        models["models"],
                    )
                )
                return models
        return models
    else:
        url = config.ollama.base_urls[url_idx]

        r = None
        try:
            r = requests.request(method="GET", url=f"{url}/api/tags")
            r.raise_for_status()

            return r.json()
        except Exception as e:
            logger.exception(e)
            error_detail = "Omni WebUI: Server Connection Error"
            if r is not None:
                try:
                    res = r.json()
                    if "error" in res:
                        error_detail = f"Ollama: {res['error']}"
                except requests.exceptions.JSONDecodeError:
                    error_detail = f"Ollama: {e}"

            raise HTTPException(
                status_code=r.status_code if r else 500,
                detail=error_detail,
            )


@app.get("/api/version")
@app.get("/api/version/{url_idx}")
async def get_ollama_versions(url_idx: Optional[int] = None):
    if app.state.config.ENABLE_OLLAMA_API:
        if url_idx is None:
            # returns lowest version
            tasks = [fetch_url(f"{url}/api/version") for url in config.ollama.base_urls]
            responses = await asyncio.gather(*tasks)
            responses = list(filter(lambda x: x is not None, responses))

            if len(responses) > 0:
                lowest_version = min(
                    responses,
                    key=lambda x: tuple(
                        map(int, re.sub(r"^v|-.*", "", x["version"]).split("."))
                    ),
                )

                return {"version": lowest_version["version"]}
            else:
                raise HTTPException(
                    status_code=500,
                    detail=ERROR_MESSAGES.OLLAMA_NOT_FOUND,
                )
        else:
            url = config.ollama.base_urls[url_idx]

            r = None
            try:
                r = requests.request(method="GET", url=f"{url}/api/version")
                r.raise_for_status()

                return r.json()
            except Exception as e:
                logger.exception(e)
                error_detail = "Omni WebUI: Server Connection Error"
                if r is not None:
                    try:
                        res = r.json()
                        if "error" in res:
                            error_detail = f"Ollama: {res['error']}"
                    except (json.JSONDecodeError, aiohttp.ContentTypeError):
                        error_detail = f"Ollama: {e}"

                raise HTTPException(
                    status_code=r.status_code if r else 500,
                    detail=error_detail,
                )
    else:
        return {"version": False}


class ModelNameForm(BaseModel):
    name: str


@app.post("/api/pull")
@app.post("/api/pull/{url_idx}")
async def pull_model(
    form_data: ModelNameForm, url_idx: int = 0, user=Depends(get_admin_user)
):
    url = config.ollama.base_urls[url_idx]
    logger.info(f"url: {url}")

    # Admin should be able to pull models from any source
    payload = {**form_data.model_dump(exclude_none=True), "insecure": True}

    return await post_streaming_url(f"{url}/api/pull", json.dumps(payload).encode())


class PushModelForm(BaseModel):
    name: str
    insecure: Optional[bool] = None
    stream: Optional[bool] = None


@app.delete("/api/push")
@app.delete("/api/push/{url_idx}")
async def push_model(
    form_data: PushModelForm,
    url_idx: Optional[int] = None,
    user=Depends(get_admin_user),
):
    if url_idx is None:
        if form_data.name in app.state.MODELS:
            url_idx = app.state.MODELS[form_data.name]["urls"][0]
        else:
            raise HTTPException(
                status_code=400,
                detail=ERROR_MESSAGES.MODEL_NOT_FOUND(form_data.name),
            )

    url = config.ollama.base_urls[url_idx]
    logger.debug(f"url: {url}")

    return await post_streaming_url(
        f"{url}/api/push", form_data.model_dump_json(exclude_none=True).encode()
    )


class CreateModelForm(BaseModel):
    name: str
    modelfile: Optional[str] = None
    stream: Optional[bool] = None
    path: Optional[str] = None


@app.post("/api/create")
@app.post("/api/create/{url_idx}")
async def create_model(
    form_data: CreateModelForm, url_idx: int = 0, user=Depends(get_admin_user)
):
    logger.debug(f"form_data: {form_data}")
    url = config.ollama.base_urls[url_idx]
    logger.info(f"url: {url}")

    return await post_streaming_url(
        f"{url}/api/create", form_data.model_dump_json(exclude_none=True).encode()
    )


class CopyModelForm(BaseModel):
    source: str
    destination: str


@app.post("/api/copy")
@app.post("/api/copy/{url_idx}")
async def copy_model(
    form_data: CopyModelForm,
    url_idx: Optional[int] = None,
    user=Depends(get_admin_user),
):
    if url_idx is None:
        if form_data.source in app.state.MODELS:
            url_idx = app.state.MODELS[form_data.source]["urls"][0]
        else:
            raise HTTPException(
                status_code=400,
                detail=ERROR_MESSAGES.MODEL_NOT_FOUND(form_data.source),
            )

    url = config.ollama.base_urls[url_idx]
    logger.info(f"url: {url}")

    try:
        r = requests.request(
            method="POST",
            url=f"{url}/api/copy",
            data=form_data.model_dump_json(exclude_none=True).encode(),
        )
        r.raise_for_status()

        logger.debug(f"r.text: {r.text}")

        return True
    except Exception as e:
        logger.exception(e)
        error_detail = "Omni WebUI: Server Connection Error"
        if r is not None:
            try:
                res = r.json()
                if "error" in res:
                    error_detail = f"Ollama: {res['error']}"
            except requests.exceptions.JSONDecodeError:
                error_detail = f"Ollama: {e}"

        raise HTTPException(
            status_code=r.status_code if r else 500,
            detail=error_detail,
        )


@app.delete("/api/delete")
@app.delete("/api/delete/{url_idx}")
async def delete_model(
    form_data: ModelNameForm,
    url_idx: Optional[int] = None,
    user=Depends(get_admin_user),
):
    if url_idx is None:
        if form_data.name in app.state.MODELS:
            url_idx = app.state.MODELS[form_data.name]["urls"][0]
        else:
            raise HTTPException(
                status_code=400,
                detail=ERROR_MESSAGES.MODEL_NOT_FOUND(form_data.name),
            )

    url = config.ollama.base_urls[url_idx]
    logger.info(f"url: {url}")

    try:
        r = requests.request(
            method="DELETE",
            url=f"{url}/api/delete",
            data=form_data.model_dump_json(exclude_none=True).encode(),
        )
        r.raise_for_status()

        logger.debug(f"r.text: {r.text}")

        return True
    except Exception as e:
        logger.exception(e)
        error_detail = "Omni WebUI: Server Connection Error"
        if r is not None:
            try:
                res = r.json()
                if "error" in res:
                    error_detail = f"Ollama: {res['error']}"
            except requests.exceptions.JSONDecodeError:
                error_detail = f"Ollama: {e}"

        raise HTTPException(
            status_code=r.status_code if r else 500,
            detail=error_detail,
        )


@app.post("/api/show")
async def show_model_info(form_data: ModelNameForm, user=Depends(get_verified_user)):
    if form_data.name not in app.state.MODELS:
        raise HTTPException(
            status_code=400,
            detail=ERROR_MESSAGES.MODEL_NOT_FOUND(form_data.name),
        )

    url_idx = random.choice(app.state.MODELS[form_data.name]["urls"])
    url = config.ollama.base_urls[url_idx]
    logger.info(f"url: {url}")

    try:
        r = requests.request(
            method="POST",
            url=f"{url}/api/show",
            data=form_data.model_dump_json(exclude_none=True).encode(),
        )
        r.raise_for_status()

        return r.json()
    except Exception as e:
        logger.exception(e)
        error_detail = "Omni WebUI: Server Connection Error"
        if r is not None:
            try:
                res = r.json()
                if "error" in res:
                    error_detail = f"Ollama: {res['error']}"
            except requests.exceptions.JSONDecodeError:
                error_detail = f"Ollama: {e}"

        raise HTTPException(
            status_code=r.status_code if r else 500,
            detail=error_detail,
        )


class GenerateEmbeddingsForm(BaseModel):
    model: str
    prompt: str
    options: Optional[dict] = None
    keep_alive: Optional[Union[int, str]] = None


@app.post("/api/embeddings")
@app.post("/api/embeddings/{url_idx}")
async def generate_embeddings(
    form_data: GenerateEmbeddingsForm,
    url_idx: Optional[int] = None,
    user=Depends(get_verified_user),
):
    if url_idx is None:
        model = form_data.model

        if ":" not in model:
            model = f"{model}:latest"

        if model in app.state.MODELS:
            url_idx = random.choice(app.state.MODELS[model]["urls"])
        else:
            raise HTTPException(
                status_code=400,
                detail=ERROR_MESSAGES.MODEL_NOT_FOUND(form_data.model),
            )

    url = config.ollama.base_urls[url_idx]
    logger.info(f"url: {url}")

    try:
        r = requests.request(
            method="POST",
            url=f"{url}/api/embeddings",
            data=form_data.model_dump_json(exclude_none=True).encode(),
        )
        r.raise_for_status()

        return r.json()
    except Exception as e:
        logger.exception(e)
        error_detail = "Omni WebUI: Server Connection Error"
        if r is not None:
            try:
                res = r.json()
                if "error" in res:
                    error_detail = f"Ollama: {res['error']}"
            except requests.exceptions.JSONDecodeError:
                error_detail = f"Ollama: {e}"

        raise HTTPException(
            status_code=r.status_code if r else 500,
            detail=error_detail,
        )


def generate_ollama_embeddings(
    form_data: GenerateEmbeddingsForm,
    url_idx: Optional[int] = None,
):
    logger.info(f"generate_ollama_embeddings {form_data}")

    if url_idx is None:
        model = form_data.model

        if ":" not in model:
            model = f"{model}:latest"

        if model in app.state.MODELS:
            url_idx = random.choice(app.state.MODELS[model]["urls"])
        else:
            raise HTTPException(
                status_code=400,
                detail=ERROR_MESSAGES.MODEL_NOT_FOUND(form_data.model),
            )

    url = config.ollama.base_urls[url_idx]
    logger.info(f"url: {url}")

    try:
        r = requests.request(
            method="POST",
            url=f"{url}/api/embeddings",
            data=form_data.model_dump_json(exclude_none=True).encode(),
        )
        r.raise_for_status()

        data = r.json()

        logger.info(f"generate_ollama_embeddings {data}")

        if "embedding" in data:
            return data["embedding"]
        else:
            raise Exception("Something went wrong :/")
    except Exception as e:
        logger.exception(e)
        error_detail = "Omni WebUI: Server Connection Error"
        if r is not None:
            try:
                res = r.json()
                if "error" in res:
                    error_detail = f"Ollama: {res['error']}"
            except requests.exceptions.JSONDecodeError:
                error_detail = f"Ollama: {e}"

        raise Exception(error_detail)


class GenerateCompletionForm(BaseModel):
    model: str
    prompt: str
    images: Optional[list[str]] = None
    format: Optional[str] = None
    options: Optional[dict] = None
    system: Optional[str] = None
    template: Optional[str] = None
    context: Optional[str] = None
    stream: Optional[bool] = True
    raw: Optional[bool] = None
    keep_alive: int | str | None = None


@app.post("/api/generate")
@app.post("/api/generate/{url_idx}")
async def generate_completion(
    form_data: GenerateCompletionForm,
    url_idx: int | None = None,
    user=Depends(get_verified_user),
):
    if url_idx is None:
        model = form_data.model

        if ":" not in model:
            model = f"{model}:latest"

        if model in app.state.MODELS:
            url_idx = random.choice(app.state.MODELS[model]["urls"])
        else:
            raise HTTPException(
                status_code=400,
                detail=ERROR_MESSAGES.MODEL_NOT_FOUND(form_data.model),
            )

    url = config.ollama.base_urls[url_idx]
    logger.info(f"url: {url}")

    return await post_streaming_url(
        f"{url}/api/generate", form_data.model_dump_json(exclude_none=True).encode()
    )


class ChatMessage(BaseModel):
    role: str
    content: str
    images: Optional[List[str]] = None


class GenerateChatCompletionForm(BaseModel):
    model: str
    messages: List[ChatMessage]
    format: Optional[str] = None
    options: Optional[dict] = None
    template: Optional[str] = None
    stream: Optional[bool] = None
    keep_alive: Optional[Union[int, str]] = None


@app.post("/api/chat")
@app.post("/api/chat/{url_idx}")
async def generate_chat_completion(
    form_data: GenerateChatCompletionForm,
    url_idx: Optional[int] = None,
    user=Depends(get_verified_user),
):
    logger.debug(f"{form_data.model_dump_json(exclude_none=True) = }")

    payload = {
        **form_data.model_dump(exclude_none=True),
    }

    model_id = form_data.model
    model_info = Models.get_model_by_id(model_id)

    if model_info:
        print(model_info)
        if model_info.base_model_id:
            payload["model"] = model_info.base_model_id

        model_params = model_info.params.model_dump()

        if model_params:
            payload["options"] = {}

            if model_params.get("mirostat"):
                payload["options"]["mirostat"] = model_params.get("mirostat")

            if model_params.get("mirostat_eta"):
                payload["options"]["mirostat_eta"] = model_params.get("mirostat_eta")

            if model_params.get("mirostat_tau"):
                payload["options"]["mirostat_tau"] = model_params.get("mirostat_tau")

            if model_params.get("num_ctx"):
                payload["options"]["num_ctx"] = model_params.get("num_ctx")

            if model_params.get("repeat_last_n"):
                payload["options"]["repeat_last_n"] = model_params.get("repeat_last_n")

            if model_params.get("frequency_penalty"):
                payload["options"]["repeat_penalty"] = model_params.get(
                    "frequency_penalty"
                )

            if model_params.get("temperature"):
                payload["options"]["temperature"] = model_params.get("temperature")

            if model_params.get("seed"):
                payload["options"]["seed"] = model_params.get("seed")

            if model_params.get("stop", None):
                payload["options"]["stop"] = (
                    [
                        bytes(stop, "utf-8").decode("unicode_escape")
                        for stop in model_params["stop"]
                    ]
                    if model_params.get("stop")
                    else None
                )

            if model_params.get("tfs_z"):
                payload["options"]["tfs_z"] = model_params.get("tfs_z")

            if model_params.get("max_tokens"):
                payload["options"]["num_predict"] = model_params.get("max_tokens")

            if model_params.get("top_k"):
                payload["options"]["top_k"] = model_params.get("top_k")

            if model_params.get("top_p"):
                payload["options"]["top_p"] = model_params.get("top_p")

            if model_params.get("use_mmap"):
                payload["options"]["use_mmap"] = model_params.get("use_mmap")

            if model_params.get("use_mlock"):
                payload["options"]["use_mlock"] = model_params.get("use_mlock")

            if model_params.get("num_thread"):
                payload["options"]["num_thread"] = model_params("num_thread")

        if model_params.get("system"):
            # Check if the payload already has a system message
            # If not, add a system message to the payload
            if payload.get("messages"):
                for message in payload["messages"]:
                    if message.get("role") == "system":
                        message["content"] = (
                            model_params.get("system") + message["content"]
                        )
                        break
                else:
                    payload["messages"].insert(
                        0,
                        {
                            "role": "system",
                            "content": model_params.get("system"),
                        },
                    )

    if url_idx is None:
        if ":" not in payload["model"]:
            payload["model"] = f"{payload['model']}:latest"

        if payload["model"] in app.state.MODELS:
            url_idx = random.choice(app.state.MODELS[payload["model"]]["urls"])
        else:
            raise HTTPException(
                status_code=400,
                detail=ERROR_MESSAGES.MODEL_NOT_FOUND(form_data.model),
            )

    url = config.ollama.base_urls[url_idx]
    logger.info(f"url: {url}")

    print(payload)

    return await post_streaming_url(f"{url}/api/chat", json.dumps(payload).encode())


# TODO: we should update this part once Ollama supports other types
class OpenAIChatMessage(BaseModel):
    role: str
    content: str

    model_config = ConfigDict(extra="allow")


class OpenAIChatCompletionForm(BaseModel):
    model: str
    messages: List[OpenAIChatMessage]

    model_config = ConfigDict(extra="allow")


@app.post("/v1/chat/completions")
@app.post("/v1/chat/completions/{url_idx}")
async def generate_openai_chat_completion(
    form_data: OpenAIChatCompletionForm,
    url_idx: Optional[int] = None,
    user=Depends(get_verified_user),
):
    payload = {
        **form_data.model_dump(exclude_none=True),
    }

    model_id = form_data.model
    model_info = Models.get_model_by_id(model_id)

    if model_info:
        print(model_info)
        if model_info.base_model_id:
            payload["model"] = model_info.base_model_id

        model_params = model_info.params.model_dump()

        if model_params:
            payload["temperature"] = model_params.get("temperature", None)
            payload["top_p"] = model_params.get("top_p", None)
            payload["max_tokens"] = model_params.get("max_tokens", None)
            payload["frequency_penalty"] = model_params.get("frequency_penalty", None)
            payload["seed"] = model_params.get("seed", None)
            payload["stop"] = (
                [
                    bytes(stop, "utf-8").decode("unicode_escape")
                    for stop in model_params["stop"]
                ]
                if model_params.get("stop", None)
                else None
            )

        if model_params.get("system", None):
            # Check if the payload already has a system message
            # If not, add a system message to the payload
            if payload.get("messages"):
                for message in payload["messages"]:
                    if message.get("role") == "system":
                        message["content"] = (
                            model_params.get("system", None) + message["content"]
                        )
                        break
                else:
                    payload["messages"].insert(
                        0,
                        {
                            "role": "system",
                            "content": model_params.get("system", None),
                        },
                    )

    if url_idx is None:
        if ":" not in payload["model"]:
            payload["model"] = f"{payload['model']}:latest"

        if payload["model"] in app.state.MODELS:
            url_idx = random.choice(app.state.MODELS[payload["model"]]["urls"])
        else:
            raise HTTPException(
                status_code=400,
                detail=ERROR_MESSAGES.MODEL_NOT_FOUND(form_data.model),
            )

    url = config.ollama.base_urls[url_idx]
    logger.info(f"url: {url}")

    return await post_streaming_url(
        f"{url}/v1/chat/completions", json.dumps(payload).encode()
    )


@app.get("/v1/models")
@app.get("/v1/models/{url_idx}")
async def get_openai_models(
    url_idx: Optional[int] = None,
    user=Depends(get_verified_user),
):
    if url_idx is None:
        models = await get_all_models()

        if config.model_filter.enabled:
            if user.role == "user":
                models["models"] = list(
                    filter(
                        lambda model: model["name"] in config.model_filter.models,
                        models["models"],
                    )
                )

        return {
            "data": [
                {
                    "id": model["model"],
                    "object": "model",
                    "created": int(time.time()),
                    "owned_by": "openai",
                }
                for model in models["models"]
            ],
            "object": "list",
        }

    else:
        url = config.ollama.base_urls[url_idx]
        try:
            r = requests.request(method="GET", url=f"{url}/api/tags")
            r.raise_for_status()

            models = r.json()

            return {
                "data": [
                    {
                        "id": model["model"],
                        "object": "model",
                        "created": int(time.time()),
                        "owned_by": "openai",
                    }
                    for model in models["models"]
                ],
                "object": "list",
            }

        except Exception as e:
            logger.exception(e)
            error_detail = "Omni WebUI: Server Connection Error"
            if r is not None:
                try:
                    res = r.json()
                    if "error" in res:
                        error_detail = f"Ollama: {res['error']}"
                except requests.exceptions.JSONDecodeError:
                    error_detail = f"Ollama: {e}"

            raise HTTPException(
                status_code=r.status_code if r else 500,
                detail=error_detail,
            )


class UrlForm(BaseModel):
    url: str


class UploadBlobForm(BaseModel):
    filename: str


def parse_huggingface_url(hf_url):
    try:
        # Parse the URL
        parsed_url = urlparse(hf_url)

        # Get the path and split it into components
        path_components = parsed_url.path.split("/")

        # Extract the desired output
        "/".join(path_components[1:3])
        model_file = path_components[-1]

        return model_file
    except ValueError:
        return None


async def download_file_stream(
    ollama_url, file_url, file_path, file_name, chunk_size=1024 * 1024
):
    done = False

    if os.path.exists(file_path):
        current_size = os.path.getsize(file_path)
    else:
        current_size = 0

    headers = {"Range": f"bytes={current_size}-"} if current_size > 0 else {}

    timeout = aiohttp.ClientTimeout(total=600)  # Set the timeout

    async with aiohttp.ClientSession(timeout=timeout, trust_env=True) as session:
        async with session.get(file_url, headers=headers) as response:
            total_size = int(response.headers.get("content-length", 0)) + current_size

            with open(file_path, "ab+") as file:
                async for data in response.content.iter_chunked(chunk_size):
                    current_size += len(data)
                    file.write(data)

                    done = current_size == total_size
                    progress = round((current_size / total_size) * 100, 2)

                    yield f'data: {{"progress": {progress}, "completed": {current_size}, "total": {total_size}}}\n\n'

                if done:
                    file.seek(0)
                    hashed = calculate_sha256(file)
                    file.seek(0)

                    url = f"{ollama_url}/api/blobs/sha256:{hashed}"
                    response = requests.post(url, data=file)

                    if response.ok:
                        res = {
                            "done": done,
                            "blob": f"sha256:{hashed}",
                            "name": file_name,
                        }
                        os.remove(file_path)

                        yield f"data: {json.dumps(res)}\n\n"
                    else:
                        raise "Ollama: Could not create blob, Please try again."


# def number_generator():
#     for i in range(1, 101):
#         yield f"data: {i}\n"


# url = "https://huggingface.co/TheBloke/stablelm-zephyr-3b-GGUF/resolve/main/stablelm-zephyr-3b.Q2_K.gguf"
@app.post("/models/download")
@app.post("/models/download/{url_idx}")
async def download_model(
    form_data: UrlForm,
    url_idx: Optional[int] = None,
):
    allowed_hosts = ["https://huggingface.co/", "https://github.com/"]

    if not any(form_data.url.startswith(host) for host in allowed_hosts):
        raise HTTPException(
            status_code=400,
            detail="Invalid file_url. Only URLs from allowed hosts are permitted.",
        )

    if url_idx is None:
        url_idx = 0
    url = config.ollama.base_urls[url_idx]

    file_name = parse_huggingface_url(form_data.url)

    if file_name:
        file_path = f"{UPLOAD_DIR}/{file_name}"

        return StreamingResponse(
            download_file_stream(url, form_data.url, file_path, file_name),
        )
    else:
        return None


@app.post("/models/upload")
@app.post("/models/upload/{url_idx}")
def upload_model(file: UploadFile = File(...), url_idx: Optional[int] = None):
    if url_idx is None:
        url_idx = 0
    ollama_url = config.ollama.base_urls[url_idx]

    file_path = f"{UPLOAD_DIR}/{file.filename}"

    # Save file in chunks
    with open(file_path, "wb+") as f:
        for chunk in file.file:
            f.write(chunk)

    def file_process_stream():
        nonlocal ollama_url
        total_size = os.path.getsize(file_path)
        chunk_size = 1024 * 1024
        try:
            with open(file_path, "rb") as f:
                total = 0
                done = False

                while not done:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        done = True
                        continue

                    total += len(chunk)
                    progress = round((total / total_size) * 100, 2)

                    res = {
                        "progress": progress,
                        "total": total_size,
                        "completed": total,
                    }
                    yield f"data: {json.dumps(res)}\n\n"

                if done:
                    f.seek(0)
                    hashed = calculate_sha256(f)
                    f.seek(0)

                    url = f"{ollama_url}/api/blobs/sha256:{hashed}"
                    response = requests.post(url, data=f)

                    if response.ok:
                        res = {
                            "done": done,
                            "blob": f"sha256:{hashed}",
                            "name": file.filename,
                        }
                        os.remove(file_path)
                        yield f"data: {json.dumps(res)}\n\n"
                    else:
                        raise Exception(
                            "Ollama: Could not create blob, Please try again."
                        )

        except Exception as e:
            res = {"error": str(e)}
            yield f"data: {json.dumps(res)}\n\n"

    return StreamingResponse(file_process_stream(), media_type="text/event-stream")
