import base64
import json
import mimetypes
import re
import uuid
from pathlib import Path
from typing import Optional

import requests
from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Request,
)
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from omni_webui.apps.images.utils.comfyui import (
    ImageGenerationPayload,
    comfyui_generate_image,
)
from omni_webui.config import (
    CACHE_DIR,
    config,
    settings,
)
from omni_webui.constants import ERROR_MESSAGES
from omni_webui.utils import (
    get_admin_user,
    get_current_user,
)
from pydantic import BaseModel, HttpUrl

IMAGE_CACHE_DIR = Path(CACHE_DIR).joinpath("./image/generations/")
IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/config")
async def get_config(request: Request, user=Depends(get_admin_user)):
    return {
        "engine": app.state.config.ENGINE,
        "enabled": app.state.config.ENABLED,
    }


class ConfigUpdateForm(BaseModel):
    engine: str
    enabled: bool


@app.post("/config/update")
async def update_config(form_data: ConfigUpdateForm, user=Depends(get_admin_user)):
    app.state.config.ENGINE = form_data.engine
    app.state.config.ENABLED = form_data.enabled
    return {
        "engine": app.state.config.ENGINE,
        "enabled": app.state.config.ENABLED,
    }


class EngineUrlUpdateForm(BaseModel):
    AUTOMATIC1111_BASE_URL: Optional[str] = None
    COMFYUI_BASE_URL: Optional[str] = None


@app.get("/url")
async def get_engine_url(user=Depends(get_admin_user)):
    return {
        "AUTOMATIC1111_BASE_URL": config.image_generation.automatic1111_base_url,
        "COMFYUI_BASE_URL": config.image_generation.comfyui_base_url,
    }


@app.post("/url/update")
async def update_engine_url(
    form_data: EngineUrlUpdateForm, user=Depends(get_admin_user)
):
    if form_data.AUTOMATIC1111_BASE_URL is not None:
        url = (form_data.AUTOMATIC1111_BASE_URL or "").strip("/")
        try:
            requests.head(url)
            config.image_generation.automatic1111_base_url = HttpUrl(url)
        except Exception as e:
            raise HTTPException(status_code=400, detail=ERROR_MESSAGES.DEFAULT(e))

    if form_data.COMFYUI_BASE_URL is not None:
        url = (form_data.COMFYUI_BASE_URL or "").strip("/")

        try:
            requests.head(url)
            config.image_generation.comfyui_base_url = HttpUrl(url)
        except Exception as e:
            raise HTTPException(status_code=400, detail=ERROR_MESSAGES.DEFAULT(e))

    return {
        "AUTOMATIC1111_BASE_URL": config.image_generation.automatic1111_base_url,
        "COMFYUI_BASE_URL": config.image_generation.comfyui_base_url,
        "status": True,
    }


class OpenAIConfigUpdateForm(BaseModel):
    url: str
    key: str


@app.get("/openai/config")
async def get_openai_config(user=Depends(get_admin_user)):
    return {
        "OPENAI_API_BASE_URL": settings.openai_api_base_url,
        "OPENAI_API_KEY": app.state.config.OPENAI_API_KEY,
    }


@app.post("/openai/config/update")
async def update_openai_config(
    form_data: OpenAIConfigUpdateForm, user=Depends(get_admin_user)
):
    if form_data.key == "":
        raise HTTPException(status_code=400, detail=ERROR_MESSAGES.API_KEY_NOT_FOUND)

    settings.openai_api_base_url = HttpUrl(form_data.url)
    settings.openai_api_key = form_data.key

    return {
        "status": True,
        "OPENAI_API_BASE_URL": settings.openai_api_base_url,
        "OPENAI_API_KEY": settings.openai_api_key,
    }


class ImageSizeUpdateForm(BaseModel):
    size: str


@app.get("/size")
async def get_image_size(user=Depends(get_admin_user)):
    return {"IMAGE_SIZE": config.image_generation.size}


@app.post("/size/update")
async def update_image_size(
    form_data: ImageSizeUpdateForm, user=Depends(get_admin_user)
):
    pattern = r"^\d+x\d+$"  # Regular expression pattern
    if re.match(pattern, form_data.size):
        config.image_generation.size = form_data.size
        return {
            "IMAGE_SIZE": config.image_generation.size,
            "status": True,
        }
    else:
        raise HTTPException(
            status_code=400,
            detail=ERROR_MESSAGES.INCORRECT_FORMAT("  (e.g., 512x512)."),
        )


class ImageStepsUpdateForm(BaseModel):
    steps: int


@app.get("/steps")
async def get_image_steps(user=Depends(get_admin_user)):
    return {"IMAGE_STEPS": config.image_generation.steps}


@app.post("/steps/update")
async def update_image_steps(
    form_data: ImageStepsUpdateForm, user=Depends(get_admin_user)
):
    if form_data.steps >= 0:
        config.image_generation.steps = form_data.steps
        return {
            "IMAGE_STEPS": config.image_generation.steps,
            "status": True,
        }
    else:
        raise HTTPException(
            status_code=400,
            detail=ERROR_MESSAGES.INCORRECT_FORMAT("  (e.g., 50)."),
        )


@app.get("/models")
def get_models(user=Depends(get_current_user)):
    try:
        if app.state.config.ENGINE == "openai":
            return [
                {"id": "dall-e-2", "name": "DALL·E 2"},
                {"id": "dall-e-3", "name": "DALL·E 3"},
            ]
        elif app.state.config.ENGINE == "comfyui":
            r = requests.get(
                url=f"{config.image_generation.comfyui_base_url}/object_info"
            )
            info = r.json()

            return list(
                map(
                    lambda model: {"id": model, "name": model},
                    info["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"][0],
                )
            )

        else:
            r = requests.get(
                url=f"{config.image_generation.automatic1111_base_url}/sdapi/v1/sd-models"
            )
            models = r.json()
            return list(
                map(
                    lambda model: {"id": model["title"], "name": model["model_name"]},
                    models,
                )
            )
    except Exception as e:
        app.state.config.ENABLED = False
        raise HTTPException(status_code=400, detail=ERROR_MESSAGES.DEFAULT(e))


@app.get("/models/default")
async def get_default_model(user=Depends(get_admin_user)):
    try:
        if app.state.config.ENGINE == "openai":
            return {
                "model": (
                    app.state.config.MODEL if app.state.config.MODEL else "dall-e-2"
                )
            }
        elif app.state.config.ENGINE == "comfyui":
            return {"model": (app.state.config.MODEL if app.state.config.MODEL else "")}
        else:
            r = requests.get(
                url=f"{config.image_generation.automatic1111_base_url}/sdapi/v1/options"
            )
            options = r.json()
            return {"model": options["sd_model_checkpoint"]}
    except Exception as e:
        app.state.config.ENABLED = False
        raise HTTPException(status_code=400, detail=ERROR_MESSAGES.DEFAULT(e))


class UpdateModelForm(BaseModel):
    model: str


def set_model_handler(model: str):
    if app.state.config.ENGINE in ["openai", "comfyui"]:
        app.state.config.MODEL = model
        return app.state.config.MODEL
    else:
        r = requests.get(
            url=f"{config.image_generation.automatic1111_base_url}/sdapi/v1/options"
        )
        options = r.json()

        if model != options["sd_model_checkpoint"]:
            options["sd_model_checkpoint"] = model
            r = requests.post(
                url=f"{config.image_generation.automatic1111_base_url}/sdapi/v1/options",
                json=options,
            )

        return options


@app.post("/models/default/update")
def update_default_model(
    form_data: UpdateModelForm,
    user=Depends(get_current_user),
):
    return set_model_handler(form_data.model)


class GenerateImageForm(BaseModel):
    model: Optional[str] = None
    prompt: str
    n: int = 1
    size: Optional[str] = None
    negative_prompt: Optional[str] = None


def save_b64_image(b64_str):
    try:
        image_id = str(uuid.uuid4())

        if "," in b64_str:
            header, encoded = b64_str.split(",", 1)
            mime_type = header.split(";")[0]

            img_data = base64.b64decode(encoded)
            image_format = mimetypes.guess_extension(mime_type)

            image_filename = f"{image_id}{image_format}"
            file_path = IMAGE_CACHE_DIR / f"{image_filename}"
            with open(file_path, "wb") as f:
                f.write(img_data)
            return image_filename
        else:
            image_filename = f"{image_id}.png"
            file_path = IMAGE_CACHE_DIR.joinpath(image_filename)

            img_data = base64.b64decode(b64_str)

            # Write the image data to a file
            with open(file_path, "wb") as f:
                f.write(img_data)
            return image_filename

    except Exception as e:
        logger.exception(f"Error saving image: {e}")
        return None


def save_url_image(url):
    image_id = str(uuid.uuid4())
    try:
        r = requests.get(url)
        r.raise_for_status()
        if r.headers["content-type"].split("/")[0] == "image":
            mime_type = r.headers["content-type"]
            image_format = mimetypes.guess_extension(mime_type)

            if not image_format:
                raise ValueError("Could not determine image type from MIME type")

            image_filename = f"{image_id}{image_format}"

            file_path = IMAGE_CACHE_DIR.joinpath(f"{image_filename}")
            with open(file_path, "wb") as image_file:
                for chunk in r.iter_content(chunk_size=8192):
                    image_file.write(chunk)
            return image_filename
        else:
            logger.error("Url does not point to an image.")
            return None

    except Exception as e:
        logger.exception(f"Error saving image: {e}")
        return None


@app.post("/generations")
def generate_image(
    form_data: GenerateImageForm,
    user=Depends(get_current_user),
):
    width, height = tuple(map(int, config.image_generation.size.split("x")))

    r = None
    try:
        if app.state.config.ENGINE == "openai":
            headers = {}
            headers["Authorization"] = f"Bearer {app.state.config.OPENAI_API_KEY}"
            headers["Content-Type"] = "application/json"

            data = {
                "model": (
                    app.state.config.MODEL
                    if app.state.config.MODEL != ""
                    else "dall-e-2"
                ),
                "prompt": form_data.prompt,
                "n": form_data.n,
                "size": (form_data.size or config.image_generation.size),
                "response_format": "b64_json",
            }

            r = requests.post(
                url=f"{settings.openai_api_base_url}/images/generations",
                json=data,
                headers=headers,
            )

            r.raise_for_status()
            res = r.json()

            images = []

            for image in res["data"]:
                image_filename = save_b64_image(image["b64_json"])
                images.append({"url": f"/cache/image/generations/{image_filename}"})
                file_body_path = IMAGE_CACHE_DIR.joinpath(f"{image_filename}.json")

                with open(file_body_path, "w") as f:
                    json.dump(data, f)

            return images

        elif app.state.config.ENGINE == "comfyui":
            data = {
                "prompt": form_data.prompt,
                "width": width,
                "height": height,
                "n": form_data.n,
            }

            if config.image_generation.steps is not None:
                data["steps"] = config.image_generation.steps

            if form_data.negative_prompt is not None:
                data["negative_prompt"] = form_data.negative_prompt

            data_ = ImageGenerationPayload(**data)

            res = comfyui_generate_image(
                app.state.config.MODEL,
                data_,
                user.id,
                config.image_generation.comfyui_base_url,
            )
            logger.debug(f"res: {res}")

            images = []

            for image in res["data"]:
                image_filename = save_url_image(image["url"])
                images.append({"url": f"/cache/image/generations/{image_filename}"})
                file_body_path = IMAGE_CACHE_DIR.joinpath(f"{image_filename}.json")

                with open(file_body_path, "w") as f:
                    json.dump(data_.model_dump(exclude_none=True), f)

            logger.debug(f"images: {images}")
            return images
        else:
            if form_data.model:
                set_model_handler(form_data.model)

            data = {
                "prompt": form_data.prompt,
                "batch_size": form_data.n,
                "width": width,
                "height": height,
            }

            if config.image_generation.steps is not None:
                data["steps"] = config.image_generation.steps

            if form_data.negative_prompt is not None:
                data["negative_prompt"] = form_data.negative_prompt

            r = requests.post(
                url=f"{config.image_generation.automatic1111_base_url}/sdapi/v1/txt2img",
                json=data,
            )

            res = r.json()

            logger.debug(f"res: {res}")

            images = []

            for image in res["images"]:
                image_filename = save_b64_image(image)
                images.append({"url": f"/cache/image/generations/{image_filename}"})
                file_body_path = IMAGE_CACHE_DIR.joinpath(f"{image_filename}.json")

                with open(file_body_path, "w") as f:
                    json.dump({**data, "info": res["info"]}, f)

            return images

    except Exception as e:
        error = e

        if r is not None:
            data = r.json()
            if "error" in data:
                error = data["error"]["message"]
        raise HTTPException(status_code=400, detail=ERROR_MESSAGES.DEFAULT(error))
