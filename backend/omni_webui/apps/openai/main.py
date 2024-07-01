import asyncio
import hashlib
import json
from pathlib import Path
from typing import Literal

import aiohttp
import requests
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from loguru import logger
from omni_webui.apps.webui.models.models import Models
from omni_webui.config import CACHE_DIR, config
from omni_webui.constants import ERROR_MESSAGES
from omni_webui.utils import (
    get_admin_user,
    get_current_user,
    get_verified_user,
)
from pydantic import BaseModel, HttpUrl
from starlette.background import BackgroundTask

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.MODELS = {}


@app.middleware("http")
async def check_url(request: Request, call_next):
    if len(app.state.MODELS) == 0:
        await get_all_models()
    else:
        pass

    response = await call_next(request)
    return response


@app.get("/config")
async def get_config(user=Depends(get_admin_user)):
    return {"ENABLE_OPENAI_API": config.openai.enable}


class OpenAIConfigForm(BaseModel):
    enable_openai_api: bool | None = None


@app.post("/config/update")
async def update_config(form_data: OpenAIConfigForm, user=Depends(get_admin_user)):
    config.openai.enable = form_data.enable_openai_api or False
    return {"ENABLE_OPENAI_API": config.openai.enable}


class UrlsUpdateForm(BaseModel):
    urls: list[HttpUrl]


class KeysUpdateForm(BaseModel):
    keys: list[str]


@app.get("/urls")
async def get_openai_urls(user=Depends(get_admin_user)):
    return {"OPENAI_API_BASE_URLS": config.openai.base_urls}


@app.post("/urls/update")
async def update_openai_urls(form_data: UrlsUpdateForm, user=Depends(get_admin_user)):
    await get_all_models()
    config.openai.base_urls = form_data.urls
    return {"OPENAI_API_BASE_URLS": config.openai.base_urls}


@app.get("/keys")
async def get_openai_keys(user=Depends(get_admin_user)):
    return {"OPENAI_API_KEYS": config.openai.api_keys}


@app.post("/keys/update")
async def update_openai_key(form_data: KeysUpdateForm, user=Depends(get_admin_user)):
    config.openai.api_keys = form_data.keys
    return {"OPENAI_API_KEYS": config.openai.api_keys}


@app.post("/audio/speech")
async def speech(request: Request, user=Depends(get_verified_user)):
    idx = None
    try:
        idx = config.openai.base_urls.index(HttpUrl("https://api.openai.com/v1"))
        body = await request.body()
        name = hashlib.sha256(body).hexdigest()

        SPEECH_CACHE_DIR = Path(CACHE_DIR).joinpath("./audio/speech/")
        SPEECH_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        file_path = SPEECH_CACHE_DIR.joinpath(f"{name}.mp3")
        file_body_path = SPEECH_CACHE_DIR.joinpath(f"{name}.json")

        # Check if the file already exists in the cache
        if file_path.is_file():
            return FileResponse(file_path)

        headers = {}
        headers["Authorization"] = f"Bearer {config.openai.api_keys[idx]}"
        headers["Content-Type"] = "application/json"
        if "openrouter.ai" in config.openai.base_urls[idx]:
            headers["HTTP-Referer"] = "https://omni-webui.com/"
            headers["X-Title"] = "Omni WebUI"
        r = None
        try:
            r = requests.post(
                url=f"{config.openai.base_urls[idx]}/audio/speech",
                data=body,
                headers=headers,
                stream=True,
            )

            r.raise_for_status()

            # Save the streaming content to a file
            with open(file_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

            with open(file_body_path, "w") as f:
                json.dump(json.loads(body.decode("utf-8")), f)

            # Return the saved file
            return FileResponse(file_path)

        except Exception as e:
            logger.exception(e)
            error_detail = "Omni WebUI: Server Connection Error"
            if r is not None:
                try:
                    res = r.json()
                    if "error" in res:
                        error_detail = f"External: {res['error']}"
                except requests.exceptions.JSONDecodeError:
                    error_detail = f"External: {e}"

            raise HTTPException(
                status_code=r.status_code if r else 500, detail=error_detail
            )

    except ValueError:
        raise HTTPException(status_code=401, detail=ERROR_MESSAGES.OPENAI_NOT_FOUND)


async def fetch_url(url, key):
    timeout = aiohttp.ClientTimeout(total=5)
    try:
        headers = {"Authorization": f"Bearer {key}"}
        async with aiohttp.ClientSession(timeout=timeout, trust_env=True) as session:
            async with session.get(url, headers=headers) as response:
                return await response.json()
    except Exception as e:
        # Handle connection error here
        logger.error(f"Connection error: {e}")
        return None


async def cleanup_response(
    response: aiohttp.ClientResponse | None,
    session: aiohttp.ClientSession | None,
):
    if response:
        response.close()
    if session:
        await session.close()


def merge_models_lists(model_lists):
    logger.debug(f"merge_models_lists {model_lists}")
    merged_list = []

    for idx, models in enumerate(model_lists):
        if models is not None and "error" not in models:
            merged_list.extend(
                [
                    {
                        **model,
                        "name": model.get("name", model["id"]),
                        "owned_by": "openai",
                        "openai": model,
                        "urlIdx": idx,
                    }
                    for model in models
                    if "api.openai.com" not in config.openai.base_urls[idx]
                    or "gpt" in model["id"]
                ]
            )

    return merged_list


async def get_all_models(raw: bool = False):
    logger.info("get_all_models()")

    models: dict[Literal["data"], list[dict]]

    if (
        len(config.openai.api_keys) == 1 and config.openai.api_keys[0] == ""
    ) or not config.openai.enable:
        models = {"data": []}
    else:
        # Check if API KEYS length is same than API URLS length
        if len(config.openai.api_keys) != len(config.openai.base_urls):
            # if there are more keys than urls, remove the extra keys
            if len(config.openai.api_keys) > len(config.openai.base_urls):
                config.openai.api_keys = config.openai.api_keys[
                    : len(config.openai.base_urls)
                ]
            # if there are more urls than keys, add empty keys
            else:
                config.openai.api_keys += [
                    ""
                    for _ in range(
                        len(config.openai.base_urls) - len(config.openai.api_keys)
                    )
                ]

        tasks = [
            fetch_url(f"{url}/models", config.openai.api_keys[idx])
            for idx, url in enumerate(config.openai.base_urls)
        ]

        responses = await asyncio.gather(*tasks)
        logger.debug(f"get_all_models:responses() {responses}")

        if raw:
            return responses

        models = {
            "data": merge_models_lists(
                list(
                    map(
                        lambda response: (
                            response["data"]
                            if (response and "data" in response)
                            else (response if isinstance(response, list) else None)
                        ),
                        responses,
                    )
                )
            )
        }

        logger.debug(f"models: {models}")
        app.state.MODELS = {model["id"]: model for model in models["data"]}

    return models


@app.get("/models")
@app.get("/models/{url_idx}")
async def get_models(url_idx: int | None = None, user=Depends(get_current_user)):
    if url_idx is None:
        models = await get_all_models()
        if config.model_filter.enabled:
            if user.role == "user":
                models["data"] = list(
                    filter(
                        lambda model: model["id"] in config.model_filter.models,
                        models["data"],
                    )
                )
                return models
        return models
    else:
        url = config.openai.base_urls[url_idx]
        key = config.openai.api_keys[url_idx]

        headers = {}
        headers["Authorization"] = f"Bearer {key}"
        headers["Content-Type"] = "application/json"

        r = None

        try:
            r = requests.request(method="GET", url=f"{url}/models", headers=headers)
            r.raise_for_status()

            response_data = r.json()
            if "api.openai.com" in url:
                response_data["data"] = list(
                    filter(lambda model: "gpt" in model["id"], response_data["data"])
                )

            return response_data
        except Exception as e:
            logger.exception(e)
            error_detail = "Omni WebUI: Server Connection Error"
            if r is not None:
                try:
                    res = r.json()
                    if "error" in res:
                        error_detail = f"External: {res['error']}"
                except requests.exceptions.JSONDecodeError:
                    error_detail = f"External: {e}"

            raise HTTPException(
                status_code=r.status_code if r else 500,
                detail=error_detail,
            )


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy(path: str, request: Request, user=Depends(get_verified_user)):
    idx = 0

    body = await request.body()
    # TODO: Remove below after gpt-4-vision fix from Open AI
    # Try to decode the body of the request from bytes to a UTF-8 string (Require add max_token to fix gpt-4-vision)

    payload: str | dict | None = None

    try:
        if "chat/completions" in path:
            body_text = body.decode("utf-8")
            body_json = json.loads(body_text)

            payload = {**body_json}

            model_id = body_json.get("model")
            model_info = Models.get_model_by_id(model_id)

            if model_info:
                logger.info(model_info)
                if model_info.base_model_id:
                    payload["model"] = model_info.base_model_id

                model_params = model_info.params.model_dump()

                if model_info.params:
                    if model_params.get("temperature", None):
                        payload["temperature"] = int(model_params.get("temperature"))  # type: ignore

                    if model_params.get("top_p", None):
                        payload["top_p"] = int(model_params.get("top_p", None))

                    if model_params.get("max_tokens", None):
                        payload["max_tokens"] = int(
                            model_params.get("max_tokens", None)
                        )

                    if model_params.get("frequency_penalty", None):
                        payload["frequency_penalty"] = int(
                            model_params.get("frequency_penalty", None)
                        )

                    if model_params.get("seed", None):
                        payload["seed"] = model_params.get("seed", None)

                    if model_params.get("stop", None):
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
                                    model_params.get("system", None)
                                    + message["content"]
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
            else:
                pass

            model = app.state.MODELS[payload.get("model")]

            idx = model["urlIdx"]

            if "pipeline" in model and model.get("pipeline"):
                payload["user"] = {"name": user.name, "id": user.id}

            # Check if the model is "gpt-4-vision-preview" and set "max_tokens" to 4000
            # This is a workaround until OpenAI fixes the issue with this model
            if payload.get("model") == "gpt-4-vision-preview":
                if "max_tokens" not in payload:
                    payload["max_tokens"] = 4000
                logger.debug("Modified payload:", payload)

            # Convert the modified body back to JSON
            payload = json.dumps(payload)

    except json.JSONDecodeError as e:
        logger.error("Error loading request body into a dictionary:", e)

    print(payload)

    url = config.openai.base_urls[idx]
    key = config.openai.api_keys[idx]

    target_url = f"{url}/{path}"

    headers = {}
    headers["Authorization"] = f"Bearer {key}"
    headers["Content-Type"] = "application/json"

    r = None
    session = None
    streaming = False

    try:
        session = aiohttp.ClientSession(trust_env=True)
        r = await session.request(
            method=request.method,
            url=target_url,
            data=payload if payload else body,
            headers=headers,
        )

        r.raise_for_status()

        # Check if response is SSE
        if "text/event-stream" in r.headers.get("Content-Type", ""):
            streaming = True
            return StreamingResponse(
                r.content,
                status_code=r.status,
                headers=dict(r.headers),
                background=BackgroundTask(
                    cleanup_response, response=r, session=session
                ),
            )
        else:
            response_data = await r.json()
            return response_data
    except Exception as e:
        logger.exception(e)
        error_detail = "Omni WebUI: Server Connection Error"
        if r is not None:
            try:
                res = await r.json()
                if "error" in res:
                    error_detail = f"External: {res['error']['message'] if 'message' in res['error'] else res['error']}"
            except (json.JSONDecodeError, aiohttp.ContentTypeError):
                error_detail = f"External: {e}"
        raise HTTPException(status_code=r.status if r else 500, detail=error_detail)
    finally:
        if not streaming and session:
            if r:
                r.close()
            await session.close()
