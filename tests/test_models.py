import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from omni_webui.models import File


@pytest.mark.anyio
async def test_file(async_session: AsyncSession, user_id: str):
    stmt = select(File)
    result = await async_session.exec(stmt)
    assert result.all() == []
    f = File(
        id="123",
        user_id=user_id,
        hash="hash",
        filename="filename",
        path="path",
        data={"data": "data"},
        meta={"meta": "meta"},
    )
    async_session.add(f)
    await async_session.commit()
    stmt = select(File)
    result = await async_session.exec(stmt)
    assert result.all() == [f]
    await async_session.delete(f)
    await async_session.commit()
