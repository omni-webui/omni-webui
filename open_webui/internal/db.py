"""Internal database module for the Open Web UI."""

import json
from contextlib import contextmanager
from typing import Any, Optional

from sqlalchemy import Dialect, create_engine, types
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.pool import NullPool, QueuePool
from sqlalchemy.sql.type_api import _T
from typing_extensions import Self

from open_webui.env import env


class JSONField(types.TypeDecorator):
    """Ridiculous!!!."""

    impl = types.Text
    cache_ok = True

    def process_bind_param(self, value: Optional[_T], dialect: Dialect) -> Any:
        """Ridiculous!!!."""
        return json.dumps(value)

    def process_result_value(self, value: Optional[_T], dialect: Dialect) -> Any:
        """Ridiculous!!!."""
        if value is not None:
            return json.loads(value)

    def copy(self, **kw: Any) -> Self:
        """Ridiculous!!!."""
        return JSONField(self.impl.length)  # type: ignore

    def db_value(self, value):
        """Ridiculous!!!."""
        return json.dumps(value)

    def python_value(self, value):
        """Ridiculous!!!."""
        if value is not None:
            return json.loads(value)


if "sqlite" in env.DATABASE_URL:
    engine = create_engine(env.DATABASE_URL, connect_args={"check_same_thread": False})
elif env.DATABASE_POOL_SIZE > 0:
    engine = create_engine(
        env.DATABASE_URL,
        pool_size=env.DATABASE_POOL_SIZE,
        max_overflow=env.DATABASE_POOL_MAX_OVERFLOW,
        pool_timeout=env.DATABASE_POOL_TIMEOUT,
        pool_recycle=env.DATABASE_POOL_RECYCLE,
        pool_pre_ping=True,
        poolclass=QueuePool,
    )
else:
    engine = create_engine(env.DATABASE_URL, pool_pre_ping=True, poolclass=NullPool)


SessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine, expire_on_commit=False
)
Base = declarative_base()
Session = scoped_session(SessionLocal)


def get_session():
    """Ridiculous!!!."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


get_db = contextmanager(get_session)
