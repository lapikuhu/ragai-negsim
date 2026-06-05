from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta, timezone
from app.core.config import settings
from fastapi.security import OAuth2PasswordBearer

# Setup password hashing context using passlib
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme for token-based authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/users/login")


def hash_password(raw: str) -> str:
    """"Hash a raw password using bcrypt.
    Args:
        raw (str): The raw password to hash.
    Returns:
        str: The hashed password."""
    return pwd_context.hash(raw)
 
def verify_password(raw: str, hashed: str) -> bool:
    """Verify a raw password against a hashed password.
    Args:
        raw (str): The raw password to verify.
        hashed (str): The hashed password to compare against.
    Returns:
        bool: True if the password matches, False otherwise."""
    return pwd_context.verify(raw, hashed)
 
def create_access_token(sub: str, session_id: int | None = None) -> str:
    """Create a JWT access token for a given subject.
    Args:
        sub (str): The subject (usually user ID) for the token.
    Returns:
        str: The encoded JWT token."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": sub, "exp": expire}
    if session_id is not None:
        payload["sid"] = session_id
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def decode_access_token(token: str) -> dict:
    """Decode a JWT access token.
    Args:
        token (str): The JWT token to decode.
    Returns:
        dict: The decoded token payload."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

def  get_password_hash(password: str) -> str:
    """Get the hashed password for a given raw password.
    Args:
        password (str): The raw password to hash.
    Returns:
        str: The hashed password."""
    return hash_password(password)
