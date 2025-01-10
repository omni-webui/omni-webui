"""Tasks router."""

from typing import Optional

import jinja2
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel

from open_webui import j2
from open_webui.config import (
    DEFAULT_EMOJI_GENERATION_PROMPT_TEMPLATE,
    DEFAULT_MOA_GENERATION_PROMPT_TEMPLATE,
    DEFAULT_QUERY_GENERATION_PROMPT_TEMPLATE,
    DEFAULT_TAGS_GENERATION_PROMPT_TEMPLATE,
    DEFAULT_TITLE_GENERATION_PROMPT_TEMPLATE,
    ConfigDBDep,
    ConfigDep,
)
from open_webui.constants import TASKS
from open_webui.models import SessionDep
from open_webui.utils.auth import get_admin_user, get_verified_user
from open_webui.utils.chat import generate_chat_completion
from open_webui.utils.task import (
    emoji_generation_template,
    get_task_model_id,
    moa_response_generation_template,
    query_generation_template,
    tags_generation_template,
    title_generation_template,
)

router = APIRouter()


@router.get("/config")
async def get_task_config(
    request: Request, config: ConfigDep, user=Depends(get_verified_user)
):
    """Get task config."""
    return {
        "TASK_MODEL": request.app.state.config.TASK_MODEL,
        "TASK_MODEL_EXTERNAL": request.app.state.config.TASK_MODEL_EXTERNAL,
        "TITLE_GENERATION_PROMPT_TEMPLATE": request.app.state.config.TITLE_GENERATION_PROMPT_TEMPLATE,
        "ENABLE_AUTOCOMPLETE_GENERATION": config.task.autocomplete.enable,
        "AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH": config.task.autocomplete.input_max_length,
        "TAGS_GENERATION_PROMPT_TEMPLATE": request.app.state.config.TAGS_GENERATION_PROMPT_TEMPLATE,
        "ENABLE_TAGS_GENERATION": request.app.state.config.ENABLE_TAGS_GENERATION,
        "ENABLE_SEARCH_QUERY_GENERATION": request.app.state.config.ENABLE_SEARCH_QUERY_GENERATION,
        "ENABLE_RETRIEVAL_QUERY_GENERATION": request.app.state.config.ENABLE_RETRIEVAL_QUERY_GENERATION,
        "QUERY_GENERATION_PROMPT_TEMPLATE": request.app.state.config.QUERY_GENERATION_PROMPT_TEMPLATE,
        "TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE": request.app.state.config.TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE,
    }


class TaskConfigForm(BaseModel):
    """Task config form."""

    TASK_MODEL: Optional[str]
    TASK_MODEL_EXTERNAL: Optional[str]
    TITLE_GENERATION_PROMPT_TEMPLATE: str
    ENABLE_AUTOCOMPLETE_GENERATION: bool
    AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH: int
    TAGS_GENERATION_PROMPT_TEMPLATE: str
    ENABLE_TAGS_GENERATION: bool
    ENABLE_SEARCH_QUERY_GENERATION: bool
    ENABLE_RETRIEVAL_QUERY_GENERATION: bool
    QUERY_GENERATION_PROMPT_TEMPLATE: str
    TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE: str


@router.post("/config/update")
async def update_task_config(
    request: Request,
    form_data: TaskConfigForm,
    session: SessionDep,
    config_db: ConfigDBDep,
    user=Depends(get_admin_user),
):
    """Update task config."""
    config = config_db.data
    request.app.state.config.TASK_MODEL = form_data.TASK_MODEL
    request.app.state.config.TASK_MODEL_EXTERNAL = form_data.TASK_MODEL_EXTERNAL
    request.app.state.config.TITLE_GENERATION_PROMPT_TEMPLATE = (
        form_data.TITLE_GENERATION_PROMPT_TEMPLATE
    )

    config.task.autocomplete.enable = form_data.ENABLE_AUTOCOMPLETE_GENERATION
    config.task.autocomplete.input_max_length = (
        form_data.AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH
    )

    request.app.state.config.TAGS_GENERATION_PROMPT_TEMPLATE = (
        form_data.TAGS_GENERATION_PROMPT_TEMPLATE
    )
    request.app.state.config.ENABLE_TAGS_GENERATION = form_data.ENABLE_TAGS_GENERATION
    request.app.state.config.ENABLE_SEARCH_QUERY_GENERATION = (
        form_data.ENABLE_SEARCH_QUERY_GENERATION
    )
    request.app.state.config.ENABLE_RETRIEVAL_QUERY_GENERATION = (
        form_data.ENABLE_RETRIEVAL_QUERY_GENERATION
    )

    request.app.state.config.QUERY_GENERATION_PROMPT_TEMPLATE = (
        form_data.QUERY_GENERATION_PROMPT_TEMPLATE
    )
    request.app.state.config.TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE = (
        form_data.TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE
    )

    config_db.data = config
    session.add(config_db)
    await session.commit()
    await session.refresh(config_db)
    config = config_db.data
    return {
        "TASK_MODEL": request.app.state.config.TASK_MODEL,
        "TASK_MODEL_EXTERNAL": request.app.state.config.TASK_MODEL_EXTERNAL,
        "TITLE_GENERATION_PROMPT_TEMPLATE": request.app.state.config.TITLE_GENERATION_PROMPT_TEMPLATE,
        "ENABLE_AUTOCOMPLETE_GENERATION": config.task.autocomplete.enable,
        "AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH": config.task.autocomplete.input_max_length,
        "TAGS_GENERATION_PROMPT_TEMPLATE": request.app.state.config.TAGS_GENERATION_PROMPT_TEMPLATE,
        "ENABLE_TAGS_GENERATION": request.app.state.config.ENABLE_TAGS_GENERATION,
        "ENABLE_SEARCH_QUERY_GENERATION": request.app.state.config.ENABLE_SEARCH_QUERY_GENERATION,
        "ENABLE_RETRIEVAL_QUERY_GENERATION": request.app.state.config.ENABLE_RETRIEVAL_QUERY_GENERATION,
        "QUERY_GENERATION_PROMPT_TEMPLATE": request.app.state.config.QUERY_GENERATION_PROMPT_TEMPLATE,
        "TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE": request.app.state.config.TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE,
    }


@router.post("/title/completions")
async def generate_title(
    request: Request, form_data: dict, user=Depends(get_verified_user)
):
    """Generate chat title."""
    models = request.app.state.MODELS

    model_id = form_data["model"]
    if model_id not in models:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found",
        )

    # Check if the user has a custom task model
    # If the user has a custom task model, use that model
    task_model_id = get_task_model_id(
        model_id,
        request.app.state.config.TASK_MODEL,
        request.app.state.config.TASK_MODEL_EXTERNAL,
        models,
    )

    logger.debug(
        f"generating chat title using model {task_model_id} for user {user.email} "
    )

    if request.app.state.config.TITLE_GENERATION_PROMPT_TEMPLATE != "":
        template = request.app.state.config.TITLE_GENERATION_PROMPT_TEMPLATE
    else:
        template = DEFAULT_TITLE_GENERATION_PROMPT_TEMPLATE

    content = title_generation_template(
        template,
        form_data["messages"],
        {
            "name": user.name,
            "location": user.info.get("location") if user.info else None,
        },
    )

    payload = {
        "model": task_model_id,
        "messages": [{"role": "user", "content": content}],
        "stream": False,
        **(
            {"max_tokens": 50}
            if models[task_model_id]["owned_by"] == "ollama"
            else {
                "max_completion_tokens": 50,
            }
        ),
        "metadata": {
            "task": str(TASKS.TITLE_GENERATION),
            "task_body": form_data,
            "chat_id": form_data.get("chat_id", None),
        },
    }

    try:
        return await generate_chat_completion(request, form_data=payload, user=user)
    except Exception:
        logger.error("Exception occurred", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "An internal error has occurred."},
        )


@router.post("/tags/completions")
async def generate_chat_tags(
    request: Request, form_data: dict, user=Depends(get_verified_user)
):
    """Generate chat tags."""
    if not request.app.state.config.ENABLE_TAGS_GENERATION:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"detail": "Tags generation is disabled"},
        )

    models = request.app.state.MODELS

    model_id = form_data["model"]
    if model_id not in models:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found",
        )

    # Check if the user has a custom task model
    # If the user has a custom task model, use that model
    task_model_id = get_task_model_id(
        model_id,
        request.app.state.config.TASK_MODEL,
        request.app.state.config.TASK_MODEL_EXTERNAL,
        models,
    )

    logger.debug(
        f"generating chat tags using model {task_model_id} for user {user.email} "
    )

    if request.app.state.config.TAGS_GENERATION_PROMPT_TEMPLATE != "":
        template = request.app.state.config.TAGS_GENERATION_PROMPT_TEMPLATE
    else:
        template = DEFAULT_TAGS_GENERATION_PROMPT_TEMPLATE

    content = tags_generation_template(
        template, form_data["messages"], {"name": user.name}
    )

    payload = {
        "model": task_model_id,
        "messages": [{"role": "user", "content": content}],
        "stream": False,
        "metadata": {
            "task": str(TASKS.TAGS_GENERATION),
            "task_body": form_data,
            "chat_id": form_data.get("chat_id", None),
        },
    }

    try:
        return await generate_chat_completion(request, form_data=payload, user=user)
    except Exception as e:
        logger.error(f"Error generating chat completion: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An internal error has occurred."},
        )


@router.post("/queries/completions")
async def generate_queries(
    request: Request, form_data: dict, user=Depends(get_verified_user)
):
    """Generate queries."""
    type = form_data.get("type")
    if type == "web_search":
        if not request.app.state.config.ENABLE_SEARCH_QUERY_GENERATION:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Search query generation is disabled",
            )
    elif type == "retrieval":
        if not request.app.state.config.ENABLE_RETRIEVAL_QUERY_GENERATION:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Query generation is disabled",
            )

    models = request.app.state.MODELS

    model_id = form_data["model"]
    if model_id not in models:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found",
        )

    # Check if the user has a custom task model
    # If the user has a custom task model, use that model
    task_model_id = get_task_model_id(
        model_id,
        request.app.state.config.TASK_MODEL,
        request.app.state.config.TASK_MODEL_EXTERNAL,
        models,
    )

    logger.debug(
        f"generating {type} queries using model {task_model_id} for user {user.email}"
    )

    if (request.app.state.config.QUERY_GENERATION_PROMPT_TEMPLATE).strip() != "":
        template = request.app.state.config.QUERY_GENERATION_PROMPT_TEMPLATE
    else:
        template = DEFAULT_QUERY_GENERATION_PROMPT_TEMPLATE

    content = query_generation_template(
        template, form_data["messages"], {"name": user.name}
    )

    payload = {
        "model": task_model_id,
        "messages": [{"role": "user", "content": content}],
        "stream": False,
        "metadata": {
            "task": str(TASKS.QUERY_GENERATION),
            "task_body": form_data,
            "chat_id": form_data.get("chat_id", None),
        },
    }

    try:
        return await generate_chat_completion(request, form_data=payload, user=user)
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(e)},
        )


class AutoCompletionForm(BaseModel):
    """Autocompletion form."""

    model: str
    prompt: str
    type: str
    messages: list
    chat_id: str | None


@router.post("/auto/completions")
async def generate_autocompletion(
    request: Request,
    form_data: AutoCompletionForm,
    config: ConfigDep,
    user=Depends(get_verified_user),
):
    """Generate autocompletion."""
    if not config.task.autocomplete.enable:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Autocompletion generation is disabled",
        )

    if config.task.autocomplete.input_max_length > 0:
        if len(form_data.prompt) > config.task.autocomplete.input_max_length:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Input prompt exceeds maximum length of {config.task.autocomplete.input_max_length}",
            )

    models = request.app.state.MODELS

    model_id = form_data.model
    if model_id not in models:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found",
        )

    # Check if the user has a custom task model
    # If the user has a custom task model, use that model
    task_model_id = get_task_model_id(
        model_id,
        request.app.state.config.TASK_MODEL,
        request.app.state.config.TASK_MODEL_EXTERNAL,
        models,
    )

    logger.debug(
        f"generating autocompletion using model {task_model_id} for user {user.email}"
    )

    template = (
        jinja2.Template(config.task.autocomplete.prompt_template)
        if config.task.autocomplete.prompt_template
        else j2.env.get_template("autocomplete.j2")
    )
    content = template.render(
        prompt=form_data.prompt,
        messages=form_data.messages,
        type=form_data.type,
        user_name=user.name,
    )

    payload = {
        "model": task_model_id,
        "messages": [{"role": "user", "content": content}],
        "stream": False,
        "metadata": {
            "task": str(TASKS.AUTOCOMPLETE_GENERATION),
            "task_body": form_data,
            "chat_id": form_data.chat_id,
        },
    }

    try:
        return await generate_chat_completion(request, form_data=payload, user=user)
    except Exception as e:
        logger.error(f"Error generating chat completion: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An internal error has occurred."},
        )


@router.post("/emoji/completions")
async def generate_emoji(
    request: Request, form_data: dict, user=Depends(get_verified_user)
):
    """Generate emoji."""
    models = request.app.state.MODELS

    model_id = form_data["model"]
    if model_id not in models:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found",
        )

    # Check if the user has a custom task model
    # If the user has a custom task model, use that model
    task_model_id = get_task_model_id(
        model_id,
        request.app.state.config.TASK_MODEL,
        request.app.state.config.TASK_MODEL_EXTERNAL,
        models,
    )

    logger.debug(f"generating emoji using model {task_model_id} for user {user.email} ")

    template = DEFAULT_EMOJI_GENERATION_PROMPT_TEMPLATE

    content = emoji_generation_template(
        template,
        form_data["prompt"],
        {
            "name": user.name,
            "location": user.info.get("location") if user.info else None,
        },
    )

    payload = {
        "model": task_model_id,
        "messages": [{"role": "user", "content": content}],
        "stream": False,
        **(
            {"max_tokens": 4}
            if models[task_model_id]["owned_by"] == "ollama"
            else {
                "max_completion_tokens": 4,
            }
        ),
        "chat_id": form_data.get("chat_id", None),
        "metadata": {"task": str(TASKS.EMOJI_GENERATION), "task_body": form_data},
    }

    try:
        return await generate_chat_completion(request, form_data=payload, user=user)
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(e)},
        )


@router.post("/moa/completions")
async def generate_moa_response(
    request: Request, form_data: dict, user=Depends(get_verified_user)
):
    """Generate MOA response."""
    models = request.app.state.MODELS
    model_id = form_data["model"]

    if model_id not in models:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found",
        )

    # Check if the user has a custom task model
    # If the user has a custom task model, use that model
    task_model_id = get_task_model_id(
        model_id,
        request.app.state.config.TASK_MODEL,
        request.app.state.config.TASK_MODEL_EXTERNAL,
        models,
    )

    logger.debug(f"generating MOA model {task_model_id} for user {user.email} ")

    template = DEFAULT_MOA_GENERATION_PROMPT_TEMPLATE

    content = moa_response_generation_template(
        template,
        form_data["prompt"],
        form_data["responses"],
    )

    payload = {
        "model": task_model_id,
        "messages": [{"role": "user", "content": content}],
        "stream": form_data.get("stream", False),
        "metadata": {
            "chat_id": form_data.get("chat_id", None),
            "task": str(TASKS.MOA_RESPONSE_GENERATION),
            "task_body": form_data,
        },
    }

    try:
        return await generate_chat_completion(request, form_data=payload, user=user)
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(e)},
        )
