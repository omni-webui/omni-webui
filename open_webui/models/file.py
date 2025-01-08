"""File model."""

from datetime import UTC, datetime
from typing import Annotated, Literal, Required, TypedDict

from openai.types.file_purpose import FilePurpose
from sqlmodel import JSON, Field, SQLModel, func

from open_webui.utils.crypto import get_random_string


class Meta(TypedDict, total=False):
    """File metadata."""

    name: Required[str]
    content_type: Required[str | None]
    size: Required[int]
    purpose: FilePurpose
    status: Literal["uploaded", "processed", "error"]
    collection_name: str


class File(SQLModel, table=True):
    """File model."""

    id: str = Field(
        primary_key=True, default_factory=lambda: f"file-{get_random_string(24)}"
    )
    user_id: str = Field(foreign_key="user.id")
    hash: str | None = None
    filename: str
    path: str | None = None
    data: Annotated[dict | None, Field(sa_type=JSON)] = None
    meta: Annotated[Meta | None, Field(sa_type=JSON)] = None
    access_control: Annotated[dict | None, Field(sa_type=JSON)] = None
    created_at: int = Field(
        default_factory=lambda: int(datetime.now(UTC).timestamp()),
        sa_column_kwargs={"server_default": func.now()},
    )
    updated_at: int = Field(
        default_factory=lambda: int(datetime.now(UTC).timestamp()),
        sa_column_kwargs={"onupdate": func.now()},
    )
