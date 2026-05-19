from models.users import User
from services import auth
from db import AsyncSession, get_session
from security import oauth2_scheme
from collections.abc import Callable
from typing import Annotated
from fastapi import Depends, HTTPException
from functools import lru_cache
from config import Settings


# --------------- SETTINGS DEPENDENCY ---------------

@lru_cache
def get_settings() -> Settings:
    return Settings()

# --------------- DATABASE DEPENDENCY ---------------

SessionDep = Annotated[AsyncSession, Depends(get_session)]
TokenDep = Annotated[str, Depends(oauth2_scheme)]


async def get_current_user(token: TokenDep, session: SessionDep) -> User:
    """Get the current authenticated user based on the provided JWT token.
    Args:
        token (str): The JWT token extracted from the Authorization header.
        session (AsyncSession): The database session for querying user data.
    Returns:
        User: The authenticated user object.
    Raises:
        HTTPException: If the token is invalid or the user cannot be authenticated."""
    user = await auth.get_current_user(token, session)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    return user


# --------------- PAGINATION DEPENDENCY ---------------

def pagination(skip: int = 0, limit: int = 20) -> dict:
    """Reusable pagination dependency.
    Args:
        skip (int): The number of items to skip.
        limit (int): The maximum number of items to return.
    Returns:
        dict: A dictionary containing the skip and limit values."""
    return {"skip": skip, "limit": limit}


Page = Annotated[dict, Depends(pagination)]