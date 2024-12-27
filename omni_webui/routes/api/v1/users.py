from fastapi import APIRouter, Depends
from sqlmodel import select

from ....deps import SessionDepends
from ....models.user import User, get_admin_user

router = APIRouter(dependencies=[Depends(get_admin_user)])


@router.get("", response_model=list[User])
async def list_users(session: SessionDepends) -> list[User]:
    return list((await session.exec(select(User))).all())
