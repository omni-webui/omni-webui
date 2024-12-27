import os
from io import BytesIO
from typing import Annotated, Literal, cast

import fsspec
from fastapi import APIRouter, Form, HTTPException, UploadFile
from openai.pagination import AsyncCursorPage
from openai.types.file_object import FileObject
from openai.types.file_purpose import FilePurpose
from sqlmodel import col, select

from ....deps import SessionDepends, SettingsDepends
from ....models._utils import now_timestamp, sha256sum
from ....models.file import File, Meta
from ....models.user import CurrentUserDepends

router = APIRouter()


@router.post("", response_model=FileObject)
async def upload_file(
    *,
    file: UploadFile,
    purpose: Annotated[FilePurpose, Form()],
    session: SessionDepends,
    user: CurrentUserDepends,
    settings: SettingsDepends,
):
    file_hash = sha256sum(await file.read())
    path = os.path.join(settings.upload_dir, file_hash)
    try:
        with fsspec.open(path, "wb") as f:
            cast(BytesIO, f).write(await file.read())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    file_info = File(
        filename=file.filename or file_hash,
        user_id=user.id,
        created_at=now_timestamp(),
        updated_at=now_timestamp(),
        path=path,
        hash=file_hash,
        meta=Meta(
            name=file.filename or file_hash,
            content_type=file.content_type,
            size=os.path.getsize(path),
            purpose=purpose,
            status="uploaded",
        ),
    )

    session.add(file_info)
    try:
        await session.commit()
        await session.refresh(file_info)
    except Exception as e:
        return {"error": str(e)}
    return file_info.to_openai()


@router.get("")
async def list_files(
    *,
    after: str | None = None,
    limit: int = 20,
    order: Literal["asc", "desc"] = "asc",
    purpose: str | None = None,
    user: CurrentUserDepends,
    session: SessionDepends,
) -> AsyncCursorPage[FileObject]:
    statement = (
        select(File)
        .where(File.user_id == user.id)
        .order_by(getattr(col(File.created_at), order)())
    )
    files = await session.exec(statement)
    data = [f.to_openai() for f in files]
    if purpose:
        data = [f for f in data if f.purpose == purpose]
    i = -1
    for i, f in enumerate(data):
        if f.id == after:
            break
    data = data[i + 1 : i + 1 + limit]
    return AsyncCursorPage[FileObject](data=data)
