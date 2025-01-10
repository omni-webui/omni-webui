"""Utility endpoints for the web UI."""

import black.report
import markdown
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from starlette.responses import FileResponse

from open_webui.config import ENABLE_ADMIN_EXPORT
from open_webui.constants import ERROR_MESSAGES
from open_webui.env import env
from open_webui.models.chats import ChatTitleMessagesForm
from open_webui.utils.auth import get_admin_user
from open_webui.utils.misc import get_gravatar_url
from open_webui.utils.pdf_generator import PDFGenerator

router = APIRouter()


@router.get("/gravatar")
async def get_gravatar(email: str):
    """Get gravatar URL."""
    return get_gravatar_url(email)


class CodeFormatRequest(BaseModel):
    """Request model for code formatting."""

    code: str


@router.post("/code/format")
async def format_code(request: CodeFormatRequest):
    """Format code using black."""
    try:
        formatted_code = black.format_str(request.code, mode=black.Mode())
        return {"code": formatted_code}
    except black.report.NothingChanged:
        return {"code": request.code}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class MarkdownForm(BaseModel):
    """Request model for markdown to HTML conversion."""

    md: str


@router.post("/markdown")
async def get_html_from_markdown(form_data: MarkdownForm):
    """Convert markdown to HTML."""
    return {"html": markdown.markdown(form_data.md)}


class ChatForm(BaseModel):
    """Request model for chat PDF generation."""

    title: str
    messages: list[dict]


@router.post("/pdf")
async def download_chat_as_pdf(form_data: ChatTitleMessagesForm):
    """Download chat as PDF."""
    pdf_bytes = PDFGenerator(form_data).generate_chat_pdf()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment;filename=chat.pdf"},
    )


@router.get("/db/download")
async def download_db(user=Depends(get_admin_user)):
    """Download the database file."""
    if not ENABLE_ADMIN_EXPORT:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )
    from open_webui.internal.db import engine

    if engine.name != "sqlite":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DB_NOT_SQLITE,
        )
    assert engine.url.database is not None
    return FileResponse(
        engine.url.database,
        media_type="application/octet-stream",
        filename="webui.db",
    )


@router.get("/litellm/config")
async def download_litellm_config_yaml(user=Depends(get_admin_user)):
    """Download the LiTeLLM config file."""
    return FileResponse(
        env.data_path / "litellm" / "config.yaml",
        media_type="application/octet-stream",
        filename="config.yaml",
    )
