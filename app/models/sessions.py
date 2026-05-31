"""
The sessions model holds user's interaction with the app during one 
user login session.
"""

from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING
from sqlmodel import Field, SQLModel, Relationship
if TYPE_CHECKING:
    from .users import User
    from .simulations import Simulation

class Session(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    session_token: str = Field(index=True, unique=True)  # Unique token for this session
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")  # The user associated with this session
    user: Optional["User"] = Relationship(back_populates="sessions")  # Relationship to the User model
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))  # Timestamp of session creation
    expires_at: datetime | None = None
    last_seen_at: datetime | None = None
    ended_at: datetime | None = None
    simulations: list["Simulation"] = Relationship(back_populates="session")