from typing import Annotated

from sqlmodel import JSON, Field, SQLModel

from ._utils import get_random_string, now_timestamp


class Chat(SQLModel, table=True):
    id: Annotated[
        str,
        Field(
            primary_key=True, default_factory=lambda: f"chat_{get_random_string(24)}"
        ),
    ]
    user_id: str
    title: str
    chat: Annotated[dict, Field(sa_type=JSON)]
    created_at: int = Field(default_factory=now_timestamp)
    updated_at: int = Field(default_factory=now_timestamp)
    share_id: str | None = None
    archived: bool = False
    pinned: bool | None = False
    meta: dict = Field(default_factory=dict, sa_type=JSON)
    folder_id: str | None = None
