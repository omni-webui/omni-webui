from fastapi import APIRouter, Depends
from sqlmodel import select

from ....deps import AsyncSessionDepends, get_admin_user
from ....models import User

router = APIRouter(dependencies=[Depends(get_admin_user)])


@router.get("/", response_model=list[User])
async def list_users(session: AsyncSessionDepends) -> list[User]:
    return list((await session.exec(select(User))).all())
