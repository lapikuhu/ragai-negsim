### ----------------------------- USERS MODELS------------------------- ###
# Models define the database structure and are used for ORM operations. 
# They are only called by repositories and services, not directly by routes.

from sqlmodel import Field, Relationship, SQLModel
from typing import TYPE_CHECKING
if TYPE_CHECKING: # Avoid circular imports by only importing Role for type checking
    from .user_roles import Role

class User(SQLModel, table=True):
    id : int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True, title="Username", min_length=3)
    hashed_password: str = Field(index=True, title="Hashed Password")
    is_admin: bool = Field(index=True, title="Is the user an admin?", default=False)
    roles: list["Role"] = Relationship(back_populates="user")