"""OpenAI API routes."""

import asyncio
import hashlib
from pathlib import Path
from typing import Optional

import aiohttp
from aiocache import cached
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from loguru import logger
from openai import AsyncOpenAI
from openai.types.audio import SpeechCreateParams
from openai.types.chat import CompletionCreateParams
from openai.types.model import Model
from pydantic import BaseModel, RootModel

from open_webui.config import CACHE_DIR, ConfigData, ConfigDBDep, ConfigDep
from open_webui.env import (
    AIOHTTP_CLIENT_TIMEOUT_OPENAI_MODEL_LIST,
    BYPASS_MODEL_ACCESS_CONTROL,
    ENABLE_FORWARD_USER_INFO_HEADERS,
    OPENAI_BASE_URL,
    ValkeyDep,
)
from open_webui.models import SessionDep
from open_webui.models.models import Models
from open_webui.utils.access_control import has_access
from open_webui.utils.auth import get_admin_user, get_verified_user
from open_webui.utils.payload import (
    apply_model_params_to_body_openai,
    apply_model_system_prompt_to_body,
)


async def send_get_request(url, key=None):
    """Send a GET request to the specified URL."""
    timeout = aiohttp.ClientTimeout(total=AIOHTTP_CLIENT_TIMEOUT_OPENAI_MODEL_LIST)
    try:
        async with aiohttp.ClientSession(timeout=timeout, trust_env=True) as session:
            async with session.get(
                url, headers={**({"Authorization": f"Bearer {key}"} if key else {})}
            ) as response:
                return await response.json()
    except Exception as e:
        # Handle connection error here
        logger.error(f"Connection error: {e}")
        return None


def openai_o1_handler(payload):
    """Handle O1 specific parameters."""
    if "max_tokens" in payload:
        # Remove "max_tokens" from the payload
        payload["max_completion_tokens"] = payload["max_tokens"]
        del payload["max_tokens"]

    # Fix: O1 does not support the "system" parameter, Modify "system" to "user"
    if payload["messages"][0]["role"] == "system":
        payload["messages"][0]["role"] = "user"

    return payload


router = APIRouter()


@router.get("/config")
async def get_config(config: ConfigDep, user=Depends(get_admin_user)):
    """Get OpenAI API configuration."""
    return {
        "ENABLE_OPENAI_API": config.openai.enable,
        "OPENAI_API_BASE_URLS": config.openai.api_base_urls,
        "OPENAI_API_KEYS": config.openai.api_keys,
        "OPENAI_API_CONFIGS": config.openai.api_configs,
    }


class OpenAIConfigForm(BaseModel):
    """OpenAI API configuration form."""

    ENABLE_OPENAI_API: Optional[bool] = None
    OPENAI_API_BASE_URLS: list[str]
    OPENAI_API_KEYS: list[str]
    OPENAI_API_CONFIGS: dict


@router.post("/config/update")
async def update_config(
    form_data: OpenAIConfigForm,
    session: SessionDep,
    config_db: ConfigDBDep,
    user=Depends(get_admin_user),
):
    """Update OpenAI API configuration."""
    config = config_db.data
    config.openai.enable = form_data.ENABLE_OPENAI_API or config.openai.enable
    config.openai.api_base_urls = form_data.OPENAI_API_BASE_URLS
    config.openai.api_keys = form_data.OPENAI_API_KEYS

    # Check if API KEYS length is same than API URLS length
    if len(config.openai.api_keys) != len(config.openai.api_base_urls):
        if len(config.openai.api_keys) > len(config.openai.api_base_urls):
            config.openai.api_keys = config.openai.api_keys[
                : len(config.openai.api_base_urls)
            ]
        else:
            config.openai.api_keys += [""] * (
                len(config.openai.api_base_urls) - len(config.openai.api_keys)
            )

    config.openai.api_configs = form_data.OPENAI_API_CONFIGS

    # Remove any extra configs
    config_urls = config.openai.api_configs.keys()
    for url in config.openai.api_base_urls:
        if url not in config_urls:
            config.openai.api_configs.pop(url, None)

    config_db.data = config
    session.add(config_db)
    await session.commit()
    await session.refresh(config_db)
    config = config_db.data
    return {
        "ENABLE_OPENAI_API": config.openai.enable,
        "OPENAI_API_BASE_URLS": config.openai.api_base_urls,
        "OPENAI_API_KEYS": config.openai.api_keys,
        "OPENAI_API_CONFIGS": config.openai.api_configs,
    }


@router.post("/audio/speech")
async def speech(
    params: RootModel[SpeechCreateParams],
    config: ConfigDep,
    user=Depends(get_verified_user),
):
    """Generate speech from text."""
    idx = config.openai.api_base_urls.index(OPENAI_BASE_URL)
    if idx == -1:
        raise HTTPException(
            status_code=404,
            detail="Open WebUI: Server Connection Error",
        )
    client = config.openai.clients[idx]

    body = params.model_dump_json().encode("utf-8")
    name = hashlib.sha256(body).hexdigest()

    SPEECH_CACHE_DIR = Path(CACHE_DIR).joinpath("./audio/speech/")
    SPEECH_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    file_path = SPEECH_CACHE_DIR.joinpath(f"{name}.mp3")
    file_body_path = SPEECH_CACHE_DIR.joinpath(f"{name}.json")

    # Check if the file already exists in the cache
    if file_path.is_file():
        return FileResponse(file_path)

    url = config.openai.api_base_urls[idx]

    async with client.audio.speech.with_streaming_response.create(
        extra_headers={
            **(
                {
                    "HTTP-Referer": "https://openwebui.com/",
                    "X-Title": "Open WebUI",
                }
                if "openrouter.ai" in url
                else {}
            ),
            **(
                {
                    "X-OpenWebUI-User-Name": user.name,
                    "X-OpenWebUI-User-Id": user.id,
                    "X-OpenWebUI-User-Email": user.email,
                    "X-OpenWebUI-User-Role": user.role,
                }
                if ENABLE_FORWARD_USER_INFO_HEADERS
                else {}
            ),
        },
        **params.root,
    ) as response:
        await response.stream_to_file(file_path)
        file_body_path.write_text(params.model_dump_json())
        return FileResponse(file_path)


async def get_all_models_responses(request: Request, config: ConfigData) -> list:
    """Get all models from OpenAI API."""
    if not config.openai.enable:
        return []

    # Check if API KEYS length is same than API URLS length
    num_urls = len(config.openai.api_base_urls)
    num_keys = len(config.openai.api_keys)

    if num_keys != num_urls:
        # if there are more keys than urls, remove the extra keys
        if num_keys > num_urls:
            new_keys = config.openai.api_keys[:num_urls]
            config.openai.api_keys = new_keys
        # if there are more urls than keys, add empty keys
        else:
            config.openai.api_keys += [""] * (num_urls - num_keys)

    request_tasks = []
    for idx, url in enumerate(config.openai.api_base_urls):
        if url not in config.openai.api_configs:
            request_tasks.append(
                send_get_request(f"{url}/models", config.openai.api_keys[idx])
            )
        else:
            api_config = config.openai.api_configs.get(url)

            enable = api_config.enable if api_config else True
            model_ids = api_config.models if api_config else []

            if enable:
                if len(model_ids) == 0:
                    request_tasks.append(
                        send_get_request(
                            f"{url}/models",
                            config.openai.api_keys[idx],
                        )
                    )
                else:
                    model_list = {
                        "object": "list",
                        "data": [
                            {
                                "id": model_id,
                                "name": model_id,
                                "owned_by": "openai",
                                "openai": {"id": model_id},
                                "urlIdx": idx,
                            }
                            for model_id in model_ids
                        ],
                    }

                    request_tasks.append(
                        asyncio.ensure_future(asyncio.sleep(0, model_list))
                    )
            else:
                request_tasks.append(asyncio.ensure_future(asyncio.sleep(0, None)))

    responses = await asyncio.gather(*request_tasks)

    for idx, response in enumerate(responses):
        if response:
            url = config.openai.api_base_urls[idx]
            api_config = config.openai.api_configs.get(url)

            prefix_id = api_config.prefix_id if api_config else None

            if prefix_id:
                for model in (
                    response if isinstance(response, list) else response.get("data", [])
                ):
                    model["id"] = f"{prefix_id}.{model['id']}"

    logger.debug(f"get_all_models:responses() {responses}")
    return responses


async def get_filtered_models(models, user):
    """Filter models based on user access control."""
    filtered_models = []
    for model in models.get("data", []):
        model_info = Models.get_model_by_id(model["id"])
        if model_info:
            if user.id == model_info.user_id or has_access(
                user.id, type="read", access_control=model_info.access_control
            ):
                filtered_models.append(model)
    return filtered_models


@cached(ttl=3)
async def get_all_models(config: ConfigDep) -> dict[str, Model]:
    """Get all models from OpenAI API."""
    result = {}

    async def list_models(client: AsyncOpenAI):
        return (await client.models.list()).data

    for future_models in asyncio.as_completed(map(list_models, config.openai.clients)):
        models = await future_models
        for model in models:
            result[model.id] = model
    return result


@router.get("/models")
@router.get("/models/{url_idx}")
async def get_models(
    *,
    url_idx: Optional[int] = None,
    config: ConfigDep,
    user=Depends(get_verified_user),
):
    """Get all models from OpenAI API."""
    models = {
        "data": [],
    }

    if url_idx is None:
        models = await get_all_models(config)
    else:
        url = config.openai.api_base_urls[url_idx]
        key = config.openai.api_keys[url_idx]

        r = None
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(
                total=AIOHTTP_CLIENT_TIMEOUT_OPENAI_MODEL_LIST
            )
        ) as session:
            try:
                async with session.get(
                    f"{url}/models",
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                        **(
                            {
                                "X-OpenWebUI-User-Name": user.name,
                                "X-OpenWebUI-User-Id": user.id,
                                "X-OpenWebUI-User-Email": user.email,
                                "X-OpenWebUI-User-Role": user.role,
                            }
                            if ENABLE_FORWARD_USER_INFO_HEADERS
                            else {}
                        ),
                    },
                ) as r:
                    if r.status != 200:
                        # Extract response error details if available
                        error_detail = f"HTTP Error: {r.status}"
                        res = await r.json()
                        if "error" in res:
                            error_detail = f"External Error: {res['error']}"
                        raise Exception(error_detail)

                    response_data = await r.json()

                    # Check if we're calling OpenAI API based on the URL
                    if "api.openai.com" in url:
                        # Filter models according to the specified conditions
                        response_data["data"] = [
                            model
                            for model in response_data.get("data", [])
                            if not any(
                                name in model["id"]
                                for name in [
                                    "babbage",
                                    "dall-e",
                                    "davinci",
                                    "embedding",
                                    "tts",
                                    "whisper",
                                ]
                            )
                        ]

                    models = response_data
            except aiohttp.ClientError as e:
                # ClientError covers all aiohttp requests issues
                logger.exception(f"Client error: {str(e)}")
                raise HTTPException(
                    status_code=500, detail="Open WebUI: Server Connection Error"
                )
            except Exception as e:
                logger.exception(f"Unexpected error: {e}")
                error_detail = f"Unexpected error: {str(e)}"
                raise HTTPException(status_code=500, detail=error_detail)

    if user.role == "user" and not BYPASS_MODEL_ACCESS_CONTROL:
        models["data"] = get_filtered_models(models, user)

    return models


class ConnectionVerificationForm(BaseModel):
    """Connection verification form."""

    url: str
    key: str


@router.post("/verify")
async def verify_connection(
    form_data: ConnectionVerificationForm, user=Depends(get_admin_user)
):
    """Verify connection to the OpenAI API."""
    url = form_data.url
    key = form_data.key

    client = AsyncOpenAI(api_key=key, base_url=url)
    return await client.models.list()


@router.post("/chat/completions")
async def generate_chat_completion(
    params: RootModel[CompletionCreateParams],
    config: ConfigDep,
    vk: ValkeyDep,
    user=Depends(get_verified_user),
    bypass_filter: bool | None = False,
):
    """Generate chat completions."""
    payload = params.root
    if BYPASS_MODEL_ACCESS_CONTROL:
        bypass_filter = True

    idx: int = 0
    model_id = payload["model"]
    model_info = Models.get_model_by_id(model_id)

    # Check model info and override the payload
    if model_info:
        if model_info.base_model_id:
            payload["model"] = model_info.base_model_id
            model_id = model_info.base_model_id

        params = model_info.params.model_dump()  # type: ignore
        payload = apply_model_params_to_body_openai(params, payload)  # type: ignore
        payload = apply_model_system_prompt_to_body(params, payload, user)  # type: ignore

        # Check if user has access to the model
        if not bypass_filter and user.role == "user":
            if not (
                user.id == model_info.user_id
                or has_access(
                    user.id, type="read", access_control=model_info.access_control
                )
            ):
                raise HTTPException(
                    status_code=403,
                    detail="Model not found",
                )
    elif not bypass_filter:
        if user.role != "admin":
            raise HTTPException(
                status_code=403,
                detail="Model not found",
            )

    openai_models = await vk.get("openai_models")
    if openai_models is None:
        openai_models = await get_all_models(config)
        vk.set("openai_models", openai_models)
    model = openai_models.get(model_id)
    if model:
        idx = model["urlIdx"]
    else:
        raise HTTPException(
            status_code=404,
            detail="Model not found",
        )

    # Get the API config for the model
    api_config = config.openai.api_configs.get(config.openai.api_base_urls[idx])

    prefix_id = api_config.prefix_id if api_config else None
    if prefix_id:
        payload["model"] = payload["model"].replace(f"{prefix_id}.", "")

    url = config.openai.api_base_urls[idx]
    client = config.openai.clients[idx]

    # Fix: O1 does not support the "max_tokens" parameter, Modify "max_tokens" to "max_completion_tokens"
    is_o1 = payload["model"].lower().startswith("o1-")
    if is_o1:
        payload = openai_o1_handler(payload)
    elif "api.openai.com" not in url:
        # Remove "max_completion_tokens" from the payload for backward compatibility
        if "max_completion_tokens" in payload:
            payload["max_tokens"] = payload["max_completion_tokens"]
            del payload["max_completion_tokens"]

    if "max_tokens" in payload and "max_completion_tokens" in payload:
        del payload["max_tokens"]

    # Convert the modified body back to JSON
    response = await client.chat.completions.create(
        extra_headers={
            **(
                {
                    "HTTP-Referer": "https://openwebui.com/",
                    "X-Title": "Open WebUI",
                }
                if "openrouter.ai" in url
                else {}
            ),
            **(
                {
                    "X-OpenWebUI-User-Name": user.name,
                    "X-OpenWebUI-User-Id": user.id,
                    "X-OpenWebUI-User-Email": user.email,
                    "X-OpenWebUI-User-Role": user.role,
                }
                if ENABLE_FORWARD_USER_INFO_HEADERS
                else {}
            ),
        },
        **RootModel[CompletionCreateParams].model_validate(payload).root,  # type: ignore
    )  # type: ignore
    return response
