from pydantic import field_validator
from datetime import datetime
from sqlmodel import Field, SQLModel


class RoleRead(SQLModel):
    id: int
    name: str


class UserCreate(SQLModel):
    username: str = Field(min_length=3, title="Username")
    password: str = Field(min_length=8, title="Password")
    role_ids: list[int] = Field(min_length=1, title="Role IDs")

    @field_validator("role_ids")
    @classmethod
    def role_ids_must_be_unique_positive(cls, role_ids: list[int]) -> list[int]:
        if any(role_id <= 0 for role_id in role_ids):
            raise ValueError("Role IDs must be positive")
        return list(dict.fromkeys(role_ids))


class UserUpdate(SQLModel):
    username: str | None = Field(default=None, min_length=3, title="Username")
    password: str | None = Field(default=None, min_length=8, title="Password")
    role_ids: list[int] | None = Field(default=None, min_length=1, title="Role IDs")

    @field_validator("role_ids")
    @classmethod
    def role_ids_must_be_unique_positive(cls, role_ids: list[int] | None) -> list[int] | None:
        if role_ids is None:
            return None
        if any(role_id <= 0 for role_id in role_ids):
            raise ValueError("Role IDs must be positive")
        return list(dict.fromkeys(role_ids))


class UserPasswordChange(SQLModel):
    current_password: str = Field(min_length=1, title="Current password")
    new_password: str = Field(min_length=8, title="New password")


class UserRead(SQLModel):
    id: int
    username: str
    roles: list[RoleRead] = Field(default_factory=list)


class UserCreatedResponse(SQLModel):
    ok: bool = True
    user: UserRead


class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"
    session_id: int | None = None
    expires_at: datetime | None = None
