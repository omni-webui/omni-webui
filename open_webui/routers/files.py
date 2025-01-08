"""Files router."""

import os
import uuid
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from loguru import logger
from pydantic import BaseModel

from open_webui.constants import ERROR_MESSAGES
from open_webui.models.files import (
    FileForm,
    FileModel,
    FileModelResponse,
    Files,
)
from open_webui.routers.retrieval import ProcessFileForm, process_file
from open_webui.storage.provider import Storage
from open_webui.utils.auth import get_admin_user, get_verified_user

router = APIRouter()


@router.post("/", response_model=FileModelResponse)
def upload_file(
    request: Request, file: UploadFile = File(...), user=Depends(get_verified_user)
):
    """Upload file."""
    logger.info(f"{file.content_type=}")
    unsanitized_filename = file.filename
    assert unsanitized_filename is not None
    filename = os.path.basename(unsanitized_filename)

    # replace filename with uuid
    id = str(uuid.uuid4())
    name = filename
    filename = f"{id}_{filename}"
    contents, file_path = Storage.upload_file(file.file, filename)

    file_item = Files.insert_new_file(
        user.id,
        FileForm(
            **{
                "id": id,
                "filename": name,
                "path": file_path,
                "meta": {
                    "name": name,
                    "content_type": file.content_type,
                    "size": len(contents),
                },
            }
        ),
    )
    assert file_item is not None

    try:
        process_file(request, ProcessFileForm(file_id=id))
        file_item = Files.get_file_by_id(id=id)
    except Exception as e:
        logger.exception(e)
        logger.error(f"Error processing file: {file_item.id}")
        file_item = FileModelResponse(
            **{
                **file_item.model_dump(),
                "error": getattr(e, "detail") if hasattr(e, "detail") else str(e),
            }
        )

    if file_item:
        return file_item
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error uploading file",
        )


@router.get("/", response_model=list[FileModelResponse])
async def list_files(user=Depends(get_verified_user)):
    """List files."""
    if user.role == "admin":
        files = Files.get_files()
    else:
        files = Files.get_files_by_user_id(user.id)
    return files


@router.delete("/all")
async def delete_all_files(user=Depends(get_admin_user)):
    """Delete all files."""
    result = Files.delete_all_files()
    if result:
        try:
            Storage.delete_all_files()
        except Exception as e:
            logger.exception(e)
            logger.error("Error deleting files")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Error deleting files",
            )
        return {"message": "All files deleted successfully"}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error deleting files",
        )


@router.get("/{id}", response_model=Optional[FileModel])
async def get_file_by_id(id: str, user=Depends(get_verified_user)):
    """Get file by id."""
    file = Files.get_file_by_id(id)

    if file and (file.user_id == user.id or user.role == "admin"):
        return file
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )


@router.get("/{id}/data/content")
async def get_file_data_content_by_id(id: str, user=Depends(get_verified_user)):
    """Get file data content by id."""
    file = Files.get_file_by_id(id)

    if file and (file.user_id == user.id or user.role == "admin"):
        return {"content": (file.data or {}).get("content", "")}
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
    request: Request, id: str, form_data: ContentForm, user=Depends(get_verified_user)
):
    """Update file data content by id."""
    file = Files.get_file_by_id(id)
    assert file is not None

    if file and (file.user_id == user.id or user.role == "admin"):
        try:
            process_file(
                request, ProcessFileForm(file_id=id, content=form_data.content)
            )
            file = Files.get_file_by_id(id=id)
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
async def get_file_content_by_id(id: str, user=Depends(get_verified_user)):
    """Get file content by id."""
    file = Files.get_file_by_id(id)
    if file and (file.user_id == user.id or user.role == "admin"):
        try:
            file_path = Storage.get_file(file.path or "")
            file_path = Path(file_path)

            # Check if the file already exists in the cache
            if file_path.is_file():
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

            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=ERROR_MESSAGES.NOT_FOUND,
                )
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


@router.get("/{id}/content/html")
async def get_html_file_content_by_id(id: str, user=Depends(get_verified_user)):
    """Get HTML file content by id."""
    file = Files.get_file_by_id(id)
    if file and (file.user_id == user.id or user.role == "admin"):
        try:
            file_path = Storage.get_file(file.path or "")
            file_path = Path(file_path)

            # Check if the file already exists in the cache
            if file_path.is_file():
                logger.info(f"{file_path=}")
                return FileResponse(file_path)
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=ERROR_MESSAGES.NOT_FOUND,
                )
        except Exception as e:
            logger.exception(e)
            logger.error("Error getting file content")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.DEFAULT("Error getting file content"),
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )


@router.get("/{id}/content/{file_name}")
async def get_file_content_by_id_and_name(id: str, user=Depends(get_verified_user)):
    """Get file content by id and file name."""
    file = Files.get_file_by_id(id)

    if file and (file.user_id == user.id or user.role == "admin"):
        file_path = file.path

        # Handle Unicode filenames
        filename = (file.meta or {}).get("name", file.filename)
        encoded_filename = quote(filename)  # RFC5987 encoding
        headers = {
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
        }

        if file_path:
            file_path = Storage.get_file(file_path)
            file_path = Path(file_path)

            # Check if the file already exists in the cache
            if file_path.is_file():
                return FileResponse(file_path, headers=headers)
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=ERROR_MESSAGES.NOT_FOUND,
                )
        else:
            # File path doesn’t exist, return the content as .txt if possible
            file_content = file.content.get("content", "")  # type: ignore

            # Create a generator that encodes the file content
            def generator():
                yield file_content.encode("utf-8")

            return StreamingResponse(
                generator(),
                media_type="text/plain",
                headers=headers,
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )


@router.delete("/{id}")
async def delete_file_by_id(id: str, user=Depends(get_verified_user)):
    """Delete file by id."""
    file = Files.get_file_by_id(id)
    if file and (file.user_id == user.id or user.role == "admin"):
        result = Files.delete_file_by_id(id)
        if result:
            try:
                Storage.delete_file(file.path or "")
            except Exception as e:
                logger.exception(e)
                logger.error("Error deleting files")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Error deleting files",
                )
            return {"message": "File deleted successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Error deleting file",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )
