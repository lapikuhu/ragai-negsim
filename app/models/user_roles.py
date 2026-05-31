from typing import TYPE_CHECKING
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .users import User
    
class Role(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, title="Role name")
    user_id: int | None = Field(default=None, foreign_key="user.id")
    # Define the relationship back to user
    user: "User" = Relationship(back_populates="roles")
