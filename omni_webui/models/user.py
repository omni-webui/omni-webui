from datetime import timedelta
from typing import TYPE_CHECKING, Annotated

import bcrypt
import jwt
from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError
from pydantic import EmailStr
from sqlalchemy.ext.mutable import MutableDict
from sqlmodel import JSON, Field, Relationship, SQLModel, select

from omni_webui.config import ConfigDepends
from omni_webui.env import EnvDepends
from omni_webui.session import SessionDepends

from .._types import MutableBaseModel
from ._utils import get_random_string, now, now_timestamp

if TYPE_CHECKING:
    from .file import File


class UserSettings(MutableBaseModel):
    ui: Annotated[dict, Field(default_factory=MutableDict)]


class User(SQLModel, table=True):
    id: str = Field(
        primary_key=True, default_factory=lambda: f"user_{get_random_string(24)}"
    )
    name: str
    email: EmailStr
    role: str = "pending"
    profile_image_url: str = "/user.png"

    last_active_at: int = Field(default_factory=now_timestamp)
    updated_at: int = Field(default_factory=now_timestamp)
    created_at: int = Field(default_factory=now_timestamp)

    api_key: str | None = None
    settings: Annotated[
        UserSettings | None, Field(sa_type=UserSettings.as_sa_type())
    ] = None  # type: ignore
    info: Annotated[
        dict | None,
        Field(sa_type=MutableDict.as_mutable(JSON), default_factory=MutableDict),  # type: ignore
    ] = None
    oauth_sub: str | None = None

    files: list["File"] = Relationship(back_populates="user")


security = HTTPBearer(auto_error=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def create_token(
    data: dict, secret_key: str, expires_delta: timedelta | None = None
) -> str:
    payload = data.copy()

    if expires_delta:
        expire = now() + expires_delta
        payload.update({"exp": expire})

    return jwt.encode(payload, secret_key, algorithm="HS256")


def decode_token(token: str, secret_key: str) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        return jwt.decode(token, secret_key, algorithms=["HS256"])
    except InvalidTokenError:
        raise credentials_exception


async def get_user(
    *,
    bearer: Annotated[HTTPAuthorizationCredentials | None, Depends(security)] = None,
    token: Annotated[str | None, Cookie()] = None,
    env: EnvDepends,
    session: SessionDepends,
    config: ConfigDepends,
) -> User | None:
    token = (bearer.credentials if bearer else None) or token
    if token is None:
        return None
    if token.startswith("sk-"):
        if not config.auth.api_key.enable:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail="Use of API key is not enabled in the environment.",
            )
        return (
            await session.exec(select(User).where(User.api_key == token))
        ).one_or_none()
    payload = decode_token(token, env.webui_secret_key)
    if "id" not in payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    user = await session.get(User, payload["id"])
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    user.last_active_at = now_timestamp()
    await session.commit()
    await session.refresh(user)
    return user


UserDepends = Annotated[User | None, Depends(get_user)]


async def get_current_user(user: UserDepends):
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    return user


CurrentUserDepends = Annotated[User, Depends(get_current_user)]


def get_admin_user(user: CurrentUserDepends):
    if user.role != "admin":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this resource. Please contact your administrator for assistance.",
        )
    return user


AdminDepends = Annotated[User, Depends(get_admin_user)]
