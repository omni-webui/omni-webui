from logging import getLogger

from pydantic import EmailStr
from sqlmodel import Field, SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from ._utils import get_random_string
from .user import User, verify_password

logger = getLogger(__name__)


class Auth(SQLModel, table=True):
    id: str = Field(
        primary_key=True, default_factory=lambda: f"user_{get_random_string(24)}"
    )  # implicit foreign key to User
    email: EmailStr
    password: str
    active: bool = True

    async def authenticate_user(
        self, password: str, session: AsyncSession
    ) -> User | None:
        logger.info(f"authenticate_user: {self.email}")

        if verify_password(password, self.password):
            return await session.get(User, self.id)
