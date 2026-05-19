from sqlmodel import Field, Relationship, SQLModel

class Role(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, title="Role name")
    user_id: int | None = Field(default=None, foreign_key="user.id")
    # Define the relationship back to user
    user: "User" = Relationship(back_populates="roles")
