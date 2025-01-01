from typing import Annotated

from sqlmodel import JSON, Field, SQLModel

from .._types import MutableBaseModel as BaseModel
from ._utils import now_timestamp


class ModelParams(BaseModel, extra="allow"): ...


class ModelMeta(BaseModel, extra="allow"): ...


class Model(SQLModel, table=True):
    id: Annotated[str, Field(primary_key=True)]
    user_id: Annotated[str, Field(foreign_key="user.id")]
    base_model_id: str | None = None
    name: str = ""
    params: ModelParams = Field(
        default_factory=ModelParams, sa_type=ModelParams.as_sa_type()
    )
    meta: ModelMeta = Field(default_factory=ModelMeta, sa_type=ModelMeta.as_sa_type())
    access_control: Annotated[dict | None, Field(sa_type=JSON, nullable=True)] = None
    is_active: bool = True
    updated_at: int = Field(default_factory=now_timestamp)
    created_at: int = Field(default_factory=now_timestamp)
