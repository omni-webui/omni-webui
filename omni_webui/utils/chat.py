import json
import random
from typing import Any

from fastapi import Request
from starlette.responses import StreamingResponse

from omni_webui.config import ConfigDepends
from omni_webui.env import Environments
from omni_webui.routers.ollama import (
    generate_chat_completion as generate_ollama_chat_completion,
)
from omni_webui.routers.openai import (
    generate_chat_completion as generate_openai_chat_completion,
)
from omni_webui.utils.models import check_model_access, get_all_models
from omni_webui.utils.payload import convert_payload_openai_to_ollama
from omni_webui.utils.response import (
    convert_response_ollama_to_openai,
    convert_streaming_response_ollama_to_openai,
)


async def generate_chat_completion(
    request: Request,
    form_data: dict,
    user: Any,
    env: Environments,
    bypass_filter: bool = False,
):
    if env.bypass_model_access_control:
        bypass_filter = True

    models = request.app.state.MODELS

    model_id = form_data["model"]
    if model_id not in models:
        raise Exception("Model not found")

    model = models[model_id]

    # Check if user has access to the model
    if not bypass_filter and user.role == "user":
        try:
            check_model_access(user, model)
        except Exception as e:
            raise e

    if model["owned_by"] == "arena":
        model_ids = model.get("info", {}).get("meta", {}).get("model_ids")
        filter_mode = model.get("info", {}).get("meta", {}).get("filter_mode")
        if model_ids and filter_mode == "exclude":
            model_ids = [
                model["id"]
                for model in list(request.app.state.MODELS.values())
                if model.get("owned_by") != "arena" and model["id"] not in model_ids
            ]

        selected_model_id = None
        if isinstance(model_ids, list) and model_ids:
            selected_model_id = random.choice(model_ids)
        else:
            model_ids = [
                model["id"]
                for model in list(request.app.state.MODELS.values())
                if model.get("owned_by") != "arena"
            ]
            selected_model_id = random.choice(model_ids)

        form_data["model"] = selected_model_id

        if form_data.get("stream"):

            async def stream_wrapper(stream):
                yield f"data: {json.dumps({'selected_model_id': selected_model_id})}\n\n"
                async for chunk in stream:
                    yield chunk

            response = await generate_chat_completion(
                request, form_data, user, env=env, bypass_filter=True
            )
            return StreamingResponse(
                stream_wrapper(response.body_iterator),
                media_type="text/event-stream",
                background=response.background,
            )
        else:
            return {
                **(
                    await generate_chat_completion(
                        request, form_data, user, env=env, bypass_filter=True
                    )
                ),
                "selected_model_id": selected_model_id,
            }

    if model["owned_by"] == "ollama":
        # Using /ollama/api/chat endpoint
        form_data = convert_payload_openai_to_ollama(form_data)
        response = await generate_ollama_chat_completion(
            request=request, form_data=form_data, user=user, bypass_filter=bypass_filter
        )
        if form_data.get("stream"):
            response.headers["content-type"] = "text/event-stream"
            return StreamingResponse(
                convert_streaming_response_ollama_to_openai(response),
                headers=dict(response.headers),
                background=response.background,
            )
        else:
            return convert_response_ollama_to_openai(response)
    else:
        return await generate_openai_chat_completion(
            request=request,
            form_data=form_data,
            user=user,
            env=env,
            bypass_filter=bypass_filter,
        )


chat_completion = generate_chat_completion


async def chat_completed(
    request: Request, form_data: dict, user: Any, config: ConfigDepends
):
    if not request.app.state.MODELS:
        await get_all_models(request, config)
    models = request.app.state.MODELS

    data = form_data
    model_id = data["model"]
    if model_id not in models:
        raise Exception("Model not found")
    return data
