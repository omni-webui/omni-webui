"""Tests for models."""

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from open_webui.models.file import File


@pytest.mark.anyio
async def test_file(session: AsyncSession, user_id: str):
    """Test file model."""
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
    )
    session.add(f)
    await session.commit()
    stmt = select(File)
    result = await session.exec(stmt)
    assert result.all() == [f]
    await session.delete(f)
    await session.commit()
