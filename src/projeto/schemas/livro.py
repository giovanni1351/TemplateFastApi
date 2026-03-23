from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlmodel import (
    Field,  # type: ignore
    Relationship,
    SQLModel,
)

if TYPE_CHECKING:
    from schemas.pagina import Pagina


class LivroCreate(SQLModel):
    nome: str


class LivroUpdate(SQLModel):
    nome: str


class Livro(LivroCreate, table=True):
    id: UUID = Field(primary_key=True, default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime | None = Field(default=None)
    deleted_at: datetime | None = Field(default=None)
    paginas: list["Pagina"] = Relationship(back_populates="livro")  # pyright: ignore[reportUnknownVariableType]
