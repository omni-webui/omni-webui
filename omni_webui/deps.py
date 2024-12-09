from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import TYPE_CHECKING, Annotated

import jwt
from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError
from passlib.context import CryptContext
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import Session, create_engine, select
from sqlmodel.ext.asyncio.session import AsyncSession

from .config import EnvironmentOnlySettings, get_env, get_settings

if TYPE_CHECKING:
    from .models.user import User


EnvDepends = Annotated[EnvironmentOnlySettings, Depends(get_env)]


@lru_cache
def get_engine(env: EnvDepends) -> Engine | AsyncEngine:
    if "aiosqlite" in env.database_url or "asyncpg" in env.database_url:
        return create_async_engine(env.database_url)
    else:
        return create_engine(env.database_url)


EngineDepends = Annotated[Engine | AsyncEngine, Depends(get_engine)]


def get_session(engine: EngineDepends):
    if isinstance(engine, AsyncEngine):
        raise TypeError("Use get_async_session for async engine")
    with Session(engine) as session:
        yield session


SessionDepends = Annotated[Session, Depends(get_session)]


async def get_async_session(engine: EngineDepends):
    if isinstance(engine, Engine):
        raise TypeError("Use get_session for sync engine")
    async with AsyncSession(engine) as session:
        yield session


AsyncSessionDepends = Annotated[AsyncSession, Depends(get_async_session)]


security = HTTPBearer(auto_error=False)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password, hashed_password):
    return (
        pwd_context.verify(plain_password, hashed_password) if hashed_password else None
    )


def get_password_hash(password):
    return pwd_context.hash(password)


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
) -> "User":
    from .models._utils import now_timestamp
    from .models.config import ConfigSettings
    from .models.user import User

    config = ConfigSettings()

    token = (bearer.credentials if bearer else None) or token
    if token is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Not authenticated")
    if token.startswith("sk-"):
        if not config.auth.api_key.enable:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail="Use of API key is not enabled in the environment.",
            )
        return (await session.exec(select(User).where(User.api_key == token))).one()
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


UserDepends = Annotated["User", Depends(get_user)]


def get_admin_user(user: UserDepends):
    if user.role != "admin":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this resource. Please contact your administrator for assistance.",
        )
    return user
