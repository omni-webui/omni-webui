import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlmodel import SQLModel

from . import __version__
from .config import Environments, Settings
from .deps import get_engine
from .models import *  # noqa
from .routes import router

env = Environments()
settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = get_engine(settings)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield


app = FastAPI(title=settings.title, version=__version__)

app.include_router(router)

os.environ["WEBUI_SECRET_KEY"] = settings.secret_key
os.environ["DATA_DIR"] = str(env.data_dir)
os.environ["FRONTEND_BUILD_DIR"] = str(settings.frontend_dir)

from open_webui.main import app as open_webui_app  # noqa: E402

app.mount("/", open_webui_app)
