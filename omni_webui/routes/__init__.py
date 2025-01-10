"""Omni WebUI routes module."""

from fastapi import APIRouter

from .mcp import router as mcp_router

router = APIRouter()
router.include_router(mcp_router, prefix="/mcp")
