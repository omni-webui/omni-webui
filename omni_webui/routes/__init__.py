from fastapi import APIRouter

from ..deps import SessionDepends
from .api import router as api_router

router = APIRouter()
router.include_router(api_router, prefix="/api")


@router.get("/health")
async def healthcheck():
    return {"status": True}


@router.get("/health/db")
async def healthcheck_with_db(session: SessionDepends):
    return {"status": True}
