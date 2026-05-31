from sqlmodel import Field, SQLModel


class RoleRead(SQLModel):
	id: int
	name: str


class UserBase(SQLModel):
	username: str = Field(min_length=3, title="Username")


class UserCreate(UserBase):
	password: str = Field(min_length=8, title="Password")


class UserLogin(SQLModel):
	username: str = Field(min_length=3, title="Username")
	password: str = Field(min_length=1, title="Password")


class UserRead(UserBase):
	id: int
	roles: list[RoleRead] = Field(default_factory=list)


class UserUpdate(SQLModel):
	username: str | None = Field(default=None, min_length=3, title="Username")
	password: str | None = Field(default=None, min_length=8, title="Password")


class Token(SQLModel):
	access_token: str
	token_type: str = "bearer"


class TokenPayload(SQLModel):
	sub: str | None = None
	exp: int | None = None
