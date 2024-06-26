from typing import List

import markdown
from fastapi import APIRouter, Depends, HTTPException, Response, status
from fpdf import FPDF
from omni_webui.config import settings
from omni_webui.constants import ERROR_MESSAGES
from omni_webui.utils import get_admin_user
from omni_webui.utils.misc import get_gravatar_url
from peewee import SqliteDatabase
from pydantic import BaseModel
from starlette.responses import FileResponse

router = APIRouter()


@router.get("/gravatar")
async def get_gravatar(
    email: str,
):
    return get_gravatar_url(email)


class MarkdownForm(BaseModel):
    md: str


@router.post("/markdown")
async def get_html_from_markdown(
    form_data: MarkdownForm,
):
    return {"html": markdown.markdown(form_data.md)}


class ChatForm(BaseModel):
    title: str
    messages: List[dict]


@router.post("/pdf")
async def download_chat_as_pdf(
    form_data: ChatForm,
):
    pdf = FPDF()
    pdf.add_page()

    FONTS_DIR = settings.static_dir / "fonts"

    pdf.add_font("NotoSans", "", FONTS_DIR / "NotoSans-Regular.ttf")
    pdf.add_font("NotoSans", "B", FONTS_DIR / "NotoSans-Bold.ttf")
    pdf.add_font("NotoSans", "I", FONTS_DIR / "NotoSans-Italic.ttf")
    pdf.add_font("NotoSansKR", "", FONTS_DIR / "NotoSansKR-Regular.ttf")
    pdf.add_font("NotoSansJP", "", FONTS_DIR / "NotoSansJP-Regular.ttf")

    pdf.set_font("NotoSans", size=12)
    pdf.set_fallback_fonts(["NotoSansKR", "NotoSansJP"])

    pdf.set_auto_page_break(auto=True, margin=15)

    # Adjust the effective page width for multi_cell
    effective_page_width = (
        pdf.w - 2 * pdf.l_margin - 10
    )  # Subtracted an additional 10 for extra padding

    # Add chat messages
    for message in form_data.messages:
        role = message["role"]
        content = message["content"]
        pdf.set_font("NotoSans", "B", size=14)  # Bold for the role
        pdf.multi_cell(effective_page_width, 10, f"{role.upper()}", 0, "L")
        pdf.ln(1)  # Extra space between messages

        pdf.set_font("NotoSans", size=10)  # Regular for content
        pdf.multi_cell(effective_page_width, 6, content, 0, "L")
        pdf.ln(1.5)  # Extra space between messages

    # Save the pdf with name .pdf
    pdf_bytes = pdf.output()

    return Response(
        content=bytes(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment;filename=chat.pdf"},
    )


@router.get("/db/download")
async def download_db(user=Depends(get_admin_user)):
    if not settings.enable_admin_export:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )
    if not isinstance(settings.database, SqliteDatabase):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DB_NOT_SQLITE,
        )
    return FileResponse(
        settings.database.database,
        media_type="application/octet-stream",
        filename="webui.db",
    )
