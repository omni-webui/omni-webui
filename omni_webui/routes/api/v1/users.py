from fastapi import APIRouter, Depends
from sqlmodel import select
from fastapi.security.api_key import APIKey


from ....deps import AsyncSessionDepends
from ....models.user import User, get_admin_user
#from ....models.apiKey import APIDepends

router = APIRouter(dependencies=[Depends(get_admin_user)])


@router.get("/", response_model=list[User])
async def list_users(session: AsyncSessionDepends) -> list[User]:
    return list((await session.exec(select(User))).all())
