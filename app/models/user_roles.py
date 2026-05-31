from typing import TYPE_CHECKING
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .users import User


class UserRoleLink(SQLModel, table=True):
    user_id: int | None = Field(default=None, foreign_key="user.id", primary_key=True)
    role_id: int | None = Field(default=None, foreign_key="role.id", primary_key=True)


class Role(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True, title="Role name")
    users: list["User"] = Relationship(back_populates="roles", link_model=UserRoleLink)
