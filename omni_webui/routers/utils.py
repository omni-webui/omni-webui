import black.report
import markdown
from fastapi import APIRouter, Depends, HTTPException, Response, status
from starlette.responses import FileResponse

from omni_webui.config import DATA_DIR, ENABLE_ADMIN_EXPORT
from omni_webui.constants import ERROR_MESSAGES
from omni_webui.utils.auth import get_admin_user
from omni_webui.utils.misc import get_gravatar_url
from omni_webui.utils.pdf_generator import PDFGenerator

router = APIRouter()


@router.get("/gravatar")
async def get_gravatar(
    email: str,
):
    return get_gravatar_url(email)


@router.post("/code/format")
async def format_code(code: str):
    try:
        formatted_code = black.format_str(code, mode=black.Mode())
        return {"code": formatted_code}
    except black.report.NothingChanged:
        return {"code": code}


@router.post("/markdown")
async def get_html_from_markdown(md: str):
    return {"html": markdown.markdown(md)}


@router.post("/pdf")
async def download_chat_as_pdf(title: str, messages: list[dict]):
    pdf_bytes = PDFGenerator(title=title, messages=messages).generate_chat_pdf()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment;filename=chat.pdf"},
    )


@router.get("/db/download")
async def download_db(user=Depends(get_admin_user)):
    if not ENABLE_ADMIN_EXPORT:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )
    from omni_webui.internal.db import engine

    if engine.name != "sqlite":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DB_NOT_SQLITE,
        )
    return FileResponse(
        engine.url.database,
        media_type="application/octet-stream",
        filename="webui.db",
    )


@router.get("/litellm/config")
async def download_litellm_config_yaml(user=Depends(get_admin_user)):
    return FileResponse(
        f"{DATA_DIR}/litellm/config.yaml",
        media_type="application/octet-stream",
        filename="config.yaml",
    )
