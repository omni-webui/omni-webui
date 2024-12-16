import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import SQLModel

from . import __version__
from ._logger import logger
from .config import get_env, get_settings
from .deps import get_engine
from .models import *  # noqa
from .routes import router

env = get_env()
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = get_engine(env)
    match engine:
        case AsyncEngine():
            async with engine.begin() as conn:
                await conn.run_sync(SQLModel.metadata.create_all)
        case Engine():
            SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title=settings.name, version=__version__)

app.include_router(router)

os.environ["FROM_INIT_PY"] = "true"

if os.getenv("WEBUI_SECRET_KEY") is None:
    os.environ["WEBUI_SECRET_KEY"] = settings.secret_key

if os.getenv("USE_CUDA_DOCKER", "false") == "true":
    logger.info(
        "CUDA is enabled, appending LD_LIBRARY_PATH to include torch/cudnn & cublas libraries."
    )
    env.LD_LIBRARY_PATH.extend(
        [
            Path("/usr/local/lib/python3.11/site-packages/torch/lib"),
            Path("/usr/local/lib/python3.11/site-packages/nvidia/cudnn/lib"),
        ]
    )
    os.environ["LD_LIBRARY_PATH"] = env.model_dump()["LD_LIBRARY_PATH"]
if env.frontend_build_dir.exists():
    os.environ["FRONTEND_BUILD_DIR"] = str(env.frontend_build_dir)

from open_webui.main import app as open_webui_app  # noqa: E402

app.mount("/", open_webui_app)
