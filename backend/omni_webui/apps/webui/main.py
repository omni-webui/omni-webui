from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from omni_webui.apps.webui.routers import (
    auths,
    chats,
    configs,
    documents,
    memories,
    models,
    prompts,
    users,
    utils,
)
from omni_webui.config import settings

app = FastAPI()

origins = ["*"]

app.state.MODELS = {}

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auths.router, prefix="/auths", tags=["auths"])
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(chats.router, prefix="/chats", tags=["chats"])

app.include_router(documents.router, prefix="/documents", tags=["documents"])
app.include_router(models.router, prefix="/models", tags=["models"])
app.include_router(prompts.router, prefix="/prompts", tags=["prompts"])
app.include_router(memories.router, prefix="/memories", tags=["memories"])

app.include_router(configs.router, prefix="/configs", tags=["configs"])
app.include_router(utils.router, prefix="/utils", tags=["utils"])


@app.get("/")
async def get_status():
    return {
        "status": True,
        "auth": settings.auth,
        "default_models": app.state.config.DEFAULT_MODELS,
        "default_prompt_suggestions": app.state.config.DEFAULT_PROMPT_SUGGESTIONS,
    }
