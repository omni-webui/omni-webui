from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Annotated

import bcrypt
import jwt
from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError
from pydantic import EmailStr
from sqlalchemy.ext.mutable import MutableDict
from sqlmodel import JSON, Field, Relationship, SQLModel, select

from .._types import MutableBaseModel
from ..config import get_settings
from ..deps import AsyncSessionDepends
from ._utils import now_timestamp
from .config import get_config

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


def create_token(data: dict, expires_delta: timedelta | None = None) -> str:
    payload = data.copy()

    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
        payload.update({"exp": expire})

    encoded_jwt = jwt.encode(payload, get_settings().secret_key, algorithm="HS256")
    return encoded_jwt


def decode_token(token: str) -> dict | None:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        decoded = jwt.decode(token, get_settings().secret_key, algorithms=["HS256"])
        return decoded
    except InvalidTokenError:
        raise credentials_exception


async def get_user(
    *,
    bearer: Annotated[HTTPAuthorizationCredentials | None, Depends(security)] = None,
    token: Annotated[str | None, Cookie()] = None,
    session: AsyncSessionDepends,
) -> User | None:
    config = await get_config()

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
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload: dict = jwt.decode(
            token, get_settings().secret_key, algorithms=["HS256"]
        )
    except InvalidTokenError:
        raise credentials_exception
    if "id" not in payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    user = await session.get(User, payload["id"])
    if user is None:
        raise credentials_exception
    user.last_active_at = now_timestamp()
    await session.commit()
    await session.refresh(user)
    return user


UserDepends = Annotated[User | None, Depends(get_user)]


def get_admin_user(user: UserDepends):
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    if user.role != "admin":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this resource. Please contact your administrator for assistance.",
        )
    return user
