"""User model."""

from typing import Annotated

import bcrypt
import jwt
from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError
from pydantic import EmailStr
from sqlalchemy.ext.mutable import MutableDict
from sqlmodel import JSON, Field, SQLModel, select

from .._types import MutableBaseModel
from ..deps import EnvDepends, SessionDepends
from ._utils import get_random_string, now_timestamp


class UserSettings(MutableBaseModel):
    """User settings model."""

    ui: Annotated[dict, Field(default_factory=MutableDict)]


class User(SQLModel, table=True):
    """User model."""

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


security = HTTPBearer(auto_error=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password."""
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


def get_password_hash(password: str) -> str:
    """Get password hash."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def decode_token(token: str, secret_key: str) -> dict:
    """Decode token."""
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
) -> User | None:
    """Get user."""
    token = (bearer.credentials if bearer else None) or token
    if token is None:
        return None
    if token.startswith("sk-"):
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
    """Get current user."""
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    return user


CurrentUserDepends = Annotated[User, Depends(get_current_user)]


def get_admin_user(user: CurrentUserDepends):
    """Get admin user."""
    if user.role != "admin":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this resource. Please contact your administrator for assistance.",
        )
    return user


AdminDepends = Annotated[User, Depends(get_admin_user)]
