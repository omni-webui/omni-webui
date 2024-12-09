from typing import Annotated

from sqlmodel import JSON, Field, Relationship, SQLModel

from ._utils import now_timestamp
from .user import User


class File(SQLModel, table=True):
    id: Annotated[str, Field(primary_key=True)]
    user_id: Annotated[str, Field(foreign_key="user.id")]
    hash: str | None
    filename: str
    path: str | None
    data: Annotated[dict | None, Field(sa_type=JSON)]
    meta: Annotated[dict | None, Field(sa_type=JSON)]
    created_at: int = Field(default_factory=now_timestamp)
    updated_at: int = Field(default_factory=now_timestamp)

    user: User = Relationship(back_populates="files")
