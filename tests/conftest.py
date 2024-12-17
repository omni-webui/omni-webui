import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from omni_webui.app import app
from omni_webui.config import get_env
from omni_webui.deps import get_session
from omni_webui.models import File, User  # noqa: F401


@pytest.fixture(name="compatible_session", scope="module")
async def compatible_session_fixture():
    env = get_env()
    engine = create_async_engine(f"sqlite+aiosqlite:///{env.data_dir / 'webui.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    session = AsyncSession(engine)
    yield session
    await session.close()


@pytest.fixture(name="session", scope="module")
async def session_fixture():
    engine = create_async_engine("sqlite+aiosqlite:///")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(engine) as session:
        yield session


@pytest.fixture(name="user_id", scope="module")
async def user_fixture(session):
    user_ = User(
        id="123",
        name="John Doe",
        email="test@example.com",
        role="admin",
        profile_image_url="https://example.org/profile.jpg",
        api_key="sk-123",
    )
    session.add(user_)
    await session.commit()
    await session.refresh(user_)
    yield user_.id
    await session.delete(user_)
    await session.commit()


@pytest.fixture(name="client", scope="module")
async def client_fixture(session: AsyncSession, user_id: str):
    app.dependency_overrides[get_session] = lambda: session
    user = await session.get_one(User, user_id)
    with TestClient(app, headers={"Authorization": f"Bearer {user.api_key}"}) as client:
        yield client
        app.dependency_overrides.clear()


@pytest.fixture(name="no_users_session")
async def no_users_session_fixture(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(engine) as session:
        yield session


@pytest.fixture(name="no_users_client")
async def no_users_client_fixture(no_users_session: AsyncSession):
    app.dependency_overrides[get_session] = lambda: no_users_session
    with TestClient(app) as client:
        yield client
        app.dependency_overrides.clear()
