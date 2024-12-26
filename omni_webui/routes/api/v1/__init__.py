from fastapi import APIRouter

from .users import router as users_router
from .files import router as file_router

router = APIRouter()

router.include_router(users_router, prefix="/users")
router.include_router(file_router, prefix="/files")
