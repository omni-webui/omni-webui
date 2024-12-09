from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import SQLModel

from .config import get_env
from .deps import get_engine
from .models import *  # noqa
from .routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = get_engine(get_env())
    match engine:
        case AsyncEngine():
            async with engine.begin() as conn:
                await conn.run_sync(SQLModel.metadata.create_all)
        case Engine():
            SQLModel.metadata.create_all(engine)
    yield


app = FastAPI()

app.include_router(router)
