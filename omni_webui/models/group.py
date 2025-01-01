from typing import Annotated

from sqlmodel import JSON, Field, SQLModel

from ._utils import now_timestamp


class Group(SQLModel, table=True):
    id: Annotated[str, Field(primary_key=True, unique=True)]
    user_id: Annotated[str, Field(foreign_key="user.id")]
    name: str = ""
    description: str = ""
    data: Annotated[dict | None, Field(sa_type=JSON, nullable=True)] = None
    user_ids: Annotated[list[str] | None, Field(sa_type=JSON, nullable=True)] = None
    created_at: int = Field(default_factory=now_timestamp)
    updated_at: int = Field(default_factory=now_timestamp)
