from typing import Any, Self, Type, cast

from pydantic import BaseModel
from sqlalchemy.ext.mutable import Mutable
from sqlalchemy.types import JSON, TypeDecorator


class BaseModelType(TypeDecorator):
    impl = JSON

    def __init__(self, pydantic_model_class: type[BaseModel], *args, **kwargs):
        self.pydantic_model_class = pydantic_model_class
        super().__init__(*args, **kwargs)

    def process_bind_param(self, value: BaseModel | None, dialect):
        return value if value is None else value.model_dump()

    def process_result_value(self, value, dialect):
        return self.pydantic_model_class.model_validate(value) if value else None


class MutableBaseModel(Mutable, BaseModel):
    def __setattr__(self, name, value):
        self.changed()
        return super().__setattr__(name, value)

    @classmethod
    def coerce(cls, key: str, value: Any) -> Self | None:
        if isinstance(value, cls) or value is None:
            return value
        if isinstance(value, str):
            return cls.model_validate_json(value)
        if isinstance(value, dict):
            return cls.model_validate(value)
        return super().coerce(key, value)

    @classmethod
    def as_sa_type(cls) -> Type:
        return cast(Type, cls.as_mutable(BaseModelType(cls)))
