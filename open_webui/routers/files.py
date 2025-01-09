"""Files router."""

import os
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import fsspec
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from loguru import logger
from pydantic import BaseModel
from sqlmodel import select

from open_webui.config import ConfigDep
from open_webui.constants import ERROR_MESSAGES
from open_webui.env import env
from open_webui.models import SessionDep
from open_webui.models.file import File as FileModel
from open_webui.models.files import FileModelResponse
from open_webui.routers.retrieval import ProcessFileForm, process_file
from open_webui.utils.auth import get_verified_user
from open_webui.utils.crypto import get_random_string

router = APIRouter()


@router.post(
    "/", response_model=FileModel, response_model_exclude={"path", "access_control"}
)
async def upload_file(
    *,
    request: Request,
    file: UploadFile = File(...),
    config: ConfigDep,
    user=Depends(get_verified_user),
    session: SessionDep,
):
    """Upload file."""
    logger.info(f"{file.content_type=}")
    unsanitized_filename = file.filename
    assert unsanitized_filename is not None
    filename = os.path.basename(unsanitized_filename)

    file_id = f"file-{get_random_string(24)}"
    file_path = f"{env.UPLOAD_DIR}/{file_id}_{filename}"
    with fsspec.open(file_path, "wb") as f:
        b = file.file.read()
        size = len(b)
        f.write(b)  # type: ignore
    file_item = FileModel(
        id=file_id,
        user_id=user.id,
        filename=filename,
        path=file_path,
        meta={
            "name": filename,
            "content_type": file.content_type,
            "size": size,
        },
    )
    session.add(file_item)
    await session.commit()
    await session.refresh(file_item)
    await process_file(request, ProcessFileForm(file_id=file_id), session)
    await session.refresh(file_item)
    return file_item


@router.get(
    "/",
    response_model=list[FileModelResponse],
    response_model_exclude={"path", "access_control"},
)
async def list_files(
    session: SessionDep,
    user=Depends(get_verified_user),
):
    """List files."""
    if user.role == "admin":
        files = (await session.exec(select(FileModel))).all()
    else:
        files = (
            await session.exec(select(FileModel).where(FileModel.user_id == user.id))
        ).all()
    return files


@router.get("/{id}", response_model=Optional[FileModel])
async def get_file_by_id(
    id: str,
    session: SessionDep,
    user=Depends(get_verified_user),
):
    """Get file by id."""
    file = await session.get_one(FileModel, id)

    if file and (file.user_id == user.id or user.role == "admin"):
        return file
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )


class ContentForm(BaseModel):
    """Request model for updating file data content."""

    content: str


@router.post("/{id}/data/content/update")
async def update_file_data_content_by_id(
    request: Request,
    id: str,
    form_data: ContentForm,
    session: SessionDep,
    user=Depends(get_verified_user),
):
    """Update file data content by id."""
    file = await session.get_one(FileModel, id)
    assert file is not None

    if file and (file.user_id == user.id or user.role == "admin"):
        try:
            await process_file(
                request, ProcessFileForm(file_id=id, content=form_data.content), session
            )
            file = await session.get_one(FileModel, id)
        except Exception as e:
            logger.exception(e)
            logger.error(f"Error processing file: {file.id}")

        assert file is not None
        return {"content": (file.data or {}).get("content", "")}
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )


@router.get("/{id}/content")
async def get_file_content_by_id(
    id: str, session: SessionDep, user=Depends(get_verified_user)
):
    """Get file content by id."""
    file = await session.get_one(FileModel, id)
    if file and (file.user_id == user.id or user.role == "admin"):
        try:
            file_path = Path(file.path or "")
            # Handle Unicode filenames
            filename = (file.meta or {}).get("name", file.filename)
            encoded_filename = quote(filename)  # RFC5987 encoding

            headers = {}
            if (file.meta or {}).get("content_type") not in [
                "application/pdf",
                "text/plain",
            ]:
                headers = {
                    **headers,
                    "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
                }

            return FileResponse(file_path, headers=headers)

        except Exception as e:
            logger.exception(e)
            logger.error("Error getting file content")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Error getting file content",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )


@router.delete("/{id}")
async def delete_file_by_id(
    id: str, session: SessionDep, user=Depends(get_verified_user)
):
    """Delete file by id."""
    file = await session.get_one(FileModel, id)
    if file and (file.user_id == user.id or user.role == "admin"):
        await session.delete(file)
        await session.flush()
        return {"message": "File deleted successfully"}
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )
