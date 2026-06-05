from fastapi import HTTPException, status
from jose import JWTError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.users import User
from app.repositories import users_repo
from app.core.security import decode_access_token

# Used by the auth deps to get the current user based on the token, 
async def get_current_user(token: str, session: AsyncSession) -> User:
    """Get the current authenticated user based on the provided JWT token.
    Args:
        token (str): The JWT token provided in the request header.
        session (AsyncSession): Database session for querying user information.
    Returns:
        User: The authenticated user corresponding to the token.
    Raises:
        HTTPException: If the token is invalid, expired, or if the user cannot be found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        username: str | None = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = await users_repo.get_user_by_username(username, session)
    if user is None:
        raise credentials_exception
    return user
