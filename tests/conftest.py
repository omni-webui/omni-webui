import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from omni_webui.app import app
from omni_webui.config import get_env
from omni_webui.deps import get_async_session
from omni_webui.models import File, User  # noqa: F401


@pytest.fixture(name="compatible_session", scope="module")
def compatible_session_fixture():
    env = get_env()
    engine = create_engine(f"sqlite:///{env.data_dir / 'webui.db'}")
    SQLModel.metadata.create_all(engine)
    session = Session(engine)
    yield session
    session.close()


@pytest.fixture(name="session", scope="module")
def session_fixture():
    engine = create_engine("sqlite:///")
    SQLModel.metadata.create_all(engine)
    session = Session(engine)
    yield session
    session.close()


@pytest.fixture(name="compatible_async_session", scope="module")
async def compatible_async_session_fixture():
    env = get_env()
    engine = create_async_engine(f"sqlite+aiosqlite:///{env.data_dir / 'webui.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    session = AsyncSession(engine)
    yield session
    await session.close()


@pytest.fixture(name="async_session", scope="module")
async def async_session_fixture():
    engine = create_async_engine("sqlite+aiosqlite:///")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(engine) as session:
        yield session


@pytest.fixture(name="user_id", scope="module")
async def user_fixture(async_session: AsyncSession):
    user_ = User(
        id="123",
        name="John Doe",
        email="test@example.com",
        role="admin",
        profile_image_url="https://example.org/profile.jpg",
        api_key="sk-123",
    )
    async_session.add(user_)
    await async_session.commit()
    await async_session.refresh(user_)
    yield user_.id
    await async_session.delete(user_)
    await async_session.commit()


@pytest.fixture(name="client", scope="module")
async def client_fixture(async_session: AsyncSession, user_id: str):
    app.dependency_overrides[get_async_session] = lambda: async_session
    user = await async_session.get_one(User, user_id)
    with TestClient(app, headers={"Authorization": f"Bearer {user.api_key}"}) as client:
        yield client
        app.dependency_overrides.clear()
