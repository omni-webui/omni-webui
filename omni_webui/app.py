import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlmodel import SQLModel

from . import __version__
from .config import Environments
from .deps import get_engine
from .models import *  # noqa
from .routes import router

env = Environments()


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = get_engine(env)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield


app = FastAPI(title=env.webui_name, version=__version__)

app.include_router(router)

os.environ["WEBUI_SECRET_KEY"] = env.webui_secret_key
os.environ["DATA_DIR"] = str(env.data_dir)
os.environ["FRONTEND_BUILD_DIR"] = str(env.frontend_build_dir)

from open_webui.main import app as open_webui_app  # noqa: E402

app.mount("/", open_webui_app)
