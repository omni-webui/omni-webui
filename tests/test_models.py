import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from omni_webui.models import File


@pytest.mark.anyio
async def test_file(session: AsyncSession, user_id: str):
    stmt = select(File)
    result = await session.exec(stmt)
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
    session.add(f)
    await session.commit()
    stmt = select(File)
    result = await session.exec(stmt)
    assert result.all() == [f]
    await session.delete(f)
    await session.commit()
