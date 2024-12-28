from fastapi import APIRouter

from .files import router as files_router
from .openai import router as openai_router
from .users import router as users_router

router = APIRouter()

router.include_router(users_router, prefix="/users")
router.include_router(files_router, prefix="/files")
router.include_router(openai_router, prefix="/openai")
