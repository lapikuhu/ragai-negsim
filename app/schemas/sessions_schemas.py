from datetime import datetime
from sqlmodel import Field, SQLModel


class SessionBase(SQLModel):
    user_id: int | None = None
    expires_at: datetime | None = None


class SessionCreate(SessionBase):
    session_token: str = Field(min_length=1)


class SessionRead(SQLModel):
    id: int
    user_id: int | None = None
    created_at: datetime
    expires_at: datetime | None = None
    last_seen_at: datetime | None = None
    ended_at: datetime | None = None


class SessionReadInternal(SessionRead):
    session_token: str


class SessionUpdate(SQLModel):
    expires_at: datetime | None = None
    last_seen_at: datetime | None = None
    ended_at: datetime | None = None


class SessionEnd(SQLModel):
    ended_at: datetime | None = None


class SessionHeartbeat(SQLModel):
    last_seen_at: datetime | None = None