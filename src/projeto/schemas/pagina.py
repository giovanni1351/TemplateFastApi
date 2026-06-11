from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlmodel import Field, Relationship, SQLModel  # type: ignore

if TYPE_CHECKING:
    from schemas.livro import Livro


class PaginaCreate(SQLModel):
    nome: str
    numero: int
    livro_id: UUID = Field(foreign_key="livro.id")


class PaginaUpdate(SQLModel):
    nome: str
    numero: int


class Pagina(PaginaCreate, table=True):
    id: UUID = Field(primary_key=True, default_factory=uuid4)

    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime | None = Field(default=None)
    deleted_at: datetime | None = Field(default=None)

    livro: "Livro" = Relationship(back_populates="paginas")  # pyright: ignore[reportUnknownVariableType]

    def __str__(self) -> str:
        return f"{self.nome} {self.id}"


class PaginaRead(SQLModel):
    id: UUID
    nome: str
    numero: int
    created_at: datetime
    updated_at: datetime | None
    deleted_at: datetime | None
    livro: "Livro"  # pyright: ignore[reportUnknownVariableType]
