from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

# Local imports
from models.user_roles import Role
from models.users import User
from security import get_password_hash
from config import settings