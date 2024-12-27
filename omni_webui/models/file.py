from typing import Annotated, Literal, Required

from openai.types import FileObject
from openai.types.file_purpose import FilePurpose
from sqlmodel import JSON, Field, Relationship, SQLModel
from typing_extensions import TypedDict

from ._utils import get_random_string, now_timestamp
from .user import User


class Meta(TypedDict, total=False):
    name: Required[str]
    content_type: Required[str | None]
    size: Required[int]
    purpose: FilePurpose
    status: Literal["uploaded", "processed", "error"]


class File(SQLModel, table=True):
    id: str = Field(
        primary_key=True, default_factory=lambda: f"file-{get_random_string(24)}"
    )
    user_id: Annotated[str, Field(foreign_key="user.id")]
    hash: str | None
    filename: str
    path: str | None
    data: Annotated[dict | None, Field(sa_type=JSON)] = None
    meta: Annotated[Meta | None, Field(sa_type=JSON)] = None
    created_at: int = Field(default_factory=now_timestamp)
    updated_at: int = Field(default_factory=now_timestamp)

    user: User = Relationship(back_populates="files")

    def to_openai(self) -> FileObject:
        meta = self.meta or {}
        return FileObject(
            id=self.id,
            bytes=meta.get("size", 0),
            created_at=self.created_at,
            filename=self.filename,
            object="file",
            purpose=meta.get("purpose", "assistants"),
            status=meta.get("status", "uploaded"),
        )
