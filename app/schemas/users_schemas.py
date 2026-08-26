from pydantic import EmailStr, field_validator
from datetime import datetime
from sqlmodel import Field, SQLModel


def _normalize_email_address(value: str | None) -> str | None:
    """
    Normalize an email address by stripping whitespace and converting to lowercase.

    Args:
        value: The email address to normalize.
    Returns:
        The normalized email address, or None if the input was None.
    """
    if value is None:
        return None
    return value.strip().lower()


class RoleRead(SQLModel):
    id: int
    name: str


class UserCreate(SQLModel):
    username: str = Field(min_length=3, title="Username")
    user_email_address: EmailStr | None = Field(default=None, title="User email address")
    password: str = Field(min_length=8, title="Password")
    role_ids: list[int] = Field(min_length=1, title="Role IDs")

    @field_validator("role_ids")
    @classmethod
    def role_ids_must_be_unique_positive(cls, role_ids: list[int]) -> list[int]:
        if any(role_id <= 0 for role_id in role_ids):
            raise ValueError("Role IDs must be positive")
        return list(dict.fromkeys(role_ids))

    @field_validator("user_email_address", mode="before")
    @classmethod
    def normalize_email_address(cls, value: str | None) -> str | None:
        return _normalize_email_address(value)


class UserUpdate(SQLModel):
    username: str | None = Field(default=None, min_length=3, title="Username")
    user_email_address: EmailStr | None = Field(default=None, title="User email address")
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

    @field_validator("user_email_address", mode="before")
    @classmethod
    def normalize_email_address(cls, value: str | None) -> str | None:
        return _normalize_email_address(value)


class UserPasswordChange(SQLModel):
    current_password: str = Field(min_length=1, title="Current password")
    new_password: str = Field(min_length=8, title="New password")


class UserRead(SQLModel):
    id: int
    username: str
    user_email_address: str | None
    roles: list[RoleRead] = Field(default_factory=list)


class UserCreatedResponse(SQLModel):
    ok: bool = True
    user: UserRead


class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"
    session_id: int | None = None
    expires_at: datetime | None = None
