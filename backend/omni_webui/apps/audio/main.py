import hashlib
import json
from pathlib import Path

import requests
from fastapi import (
    Depends,
    FastAPI,
    File,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from faster_whisper import WhisperModel
from loguru import logger
from omni_webui.config import (
    CACHE_DIR,
    DEVICE_TYPE,
    UPLOAD_DIR,
    WHISPER_MODEL,
    WHISPER_MODEL_AUTO_UPDATE,
    WHISPER_MODEL_DIR,
    settings,
)
from omni_webui.constants import ERROR_MESSAGES
from omni_webui.utils import (
    get_admin_user,
    get_current_user,
    get_verified_user,
)
from pydantic import BaseModel, HttpUrl

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# setting device type for whisper model
whisper_device_type = DEVICE_TYPE if DEVICE_TYPE and DEVICE_TYPE == "cuda" else "cpu"
logger.info(f"whisper_device_type: {whisper_device_type}")

SPEECH_CACHE_DIR = Path(CACHE_DIR).joinpath("./audio/speech/")
SPEECH_CACHE_DIR.mkdir(parents=True, exist_ok=True)


class OpenAIConfigUpdateForm(BaseModel):
    url: str
    key: str
    model: str
    speaker: str


@app.get("/config")
async def get_openai_config(user=Depends(get_admin_user)):
    return {
        "OPENAI_API_BASE_URL": settings.openai_api_base_url,
        "OPENAI_API_KEY": settings.openai_api_key,
        "OPENAI_API_MODEL": app.state.config.OPENAI_API_MODEL,
        "OPENAI_API_VOICE": app.state.config.OPENAI_API_VOICE,
    }


@app.post("/config/update")
async def update_openai_config(
    form_data: OpenAIConfigUpdateForm, user=Depends(get_admin_user)
):
    if form_data.key == "":
        raise HTTPException(status_code=400, detail=ERROR_MESSAGES.API_KEY_NOT_FOUND)

    settings.openai_api_base_url = HttpUrl(form_data.url)
    settings.openai_api_key = form_data.key
    app.state.config.OPENAI_API_MODEL = form_data.model
    app.state.config.OPENAI_API_VOICE = form_data.speaker

    return {
        "status": True,
        "OPENAI_API_BASE_URL": settings.openai_api_base_url,
        "OPENAI_API_KEY": settings.openai_api_key,
        "OPENAI_API_MODEL": app.state.config.OPENAI_API_MODEL,
        "OPENAI_API_VOICE": app.state.config.OPENAI_API_VOICE,
    }


@app.post("/speech")
async def speech(request: Request, user=Depends(get_verified_user)):
    body = await request.body()
    name = hashlib.sha256(body).hexdigest()

    file_path = SPEECH_CACHE_DIR.joinpath(f"{name}.mp3")
    file_body_path = SPEECH_CACHE_DIR.joinpath(f"{name}.json")

    # Check if the file already exists in the cache
    if file_path.is_file():
        return FileResponse(file_path)

    headers = {}
    headers["Authorization"] = f"Bearer {app.state.config.OPENAI_API_KEY}"
    headers["Content-Type"] = "application/json"

    r = None
    try:
        r = requests.post(
            url=f"{settings.openai_api_base_url}/audio/speech",
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
                    error_detail = f"External: {res['error']['message']}"
            except requests.exceptions.JSONDecodeError:
                error_detail = f"External: {e}"

        raise HTTPException(
            status_code=r.status_code if r is not None else 500,
            detail=error_detail,
        )


@app.post("/transcriptions")
def transcribe(
    file: UploadFile = File(...),
    user=Depends(get_current_user),
):
    logger.info(f"file.content_type: {file.content_type}")

    if file.content_type not in ["audio/mpeg", "audio/wav"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.FILE_NOT_SUPPORTED,
        )

    try:
        filename = file.filename
        file_path = f"{UPLOAD_DIR}/{filename}"
        contents = file.file.read()
        with open(file_path, "wb") as f:
            f.write(contents)
            f.close()

        whisper_kwargs = {
            "model_size_or_path": WHISPER_MODEL,
            "device": whisper_device_type,
            "compute_type": "int8",
            "download_root": WHISPER_MODEL_DIR,
            "local_files_only": not WHISPER_MODEL_AUTO_UPDATE,
        }

        logger.debug(f"whisper_kwargs: {whisper_kwargs}")

        try:
            model = WhisperModel(**whisper_kwargs)
        except Exception:
            logger.warning(
                "WhisperModel initialization failed, attempting download with local_files_only=False"
            )
            whisper_kwargs["local_files_only"] = False
            model = WhisperModel(**whisper_kwargs)

        segments, info = model.transcribe(file_path, beam_size=5)
        logger.info(
            "Detected language '%s' with probability %f"
            % (info.language, info.language_probability)
        )

        transcript = "".join([segment.text for segment in list(segments)])

        return {"text": transcript.strip()}

    except Exception as e:
        logger.exception(e)

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(e),
        )
