from typing import TYPE_CHECKING, Annotated

from pydantic import EmailStr
from sqlalchemy.ext.mutable import MutableDict
from sqlmodel import JSON, Field, Relationship, SQLModel

from ._types import MutableBaseModel
from ._utils import now_timestamp

if TYPE_CHECKING:
    from .file import File


class UserSettings(MutableBaseModel):
    ui: Annotated[dict, Field(default_factory=MutableDict)]


class User(SQLModel, table=True):
    id: Annotated[str, Field(primary_key=True)]
    name: str
    email: EmailStr
    role: str
    profile_image_url: str

    last_active_at: int = Field(default_factory=now_timestamp)
    updated_at: int = Field(default_factory=now_timestamp)
    created_at: int = Field(default_factory=now_timestamp)

    api_key: str | None = None
    settings: Annotated[dict | None, Field(sa_type=UserSettings.as_sa_type())] = None  # type: ignore
    info: Annotated[
        dict | None,
        Field(sa_type=MutableDict.as_mutable(JSON), default_factory=MutableDict),  # type: ignore
    ] = None
    oauth_sub: str | None = None

    files: list["File"] = Relationship(back_populates="user")
