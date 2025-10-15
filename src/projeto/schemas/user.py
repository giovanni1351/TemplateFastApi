from datetime import datetime
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel  # pyright: ignore[reportUnknownVariableType]


class UserCreate(SQLModel):
    nome: str | None = None
    username: str = Field(unique=True)
    sobrenome: str
    idade: int
    cpf: str
    senha: str
    email: str = Field(default="sem_email@gmail.com")
    password: str


class User(UserCreate, table=True):
    id: UUID = Field(primary_key=True, default_factory=uuid4)
    is_admin: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime | None = Field(default=None)
    deleted_at: datetime | None = Field(default=None)
