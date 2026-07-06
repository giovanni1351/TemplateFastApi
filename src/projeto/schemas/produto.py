# Gerado pelo gerenciador do template. Edite via `python gerenciar.py` ou manualmente.
from datetime import date, datetime
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel  # pyright: ignore[reportUnknownVariableType]


class ProdutoCreate(SQLModel):
    nome: str
    descricao: str | None = None
    sku: str = Field(unique=True)
    preco: float = 0.0
    estoque: int = 0
    ativo: bool = True
    categoria: str = Field(index=True)
    peso_kg: float | None = None
    codigo_barras: str | None = Field(default=None, unique=True)
    lancamento: date | None = None


class ProdutoUpdate(SQLModel):
    nome: str | None = None
    descricao: str | None = None
    preco: float | None = None
    estoque: int | None = None
    ativo: bool | None = None
    categoria: str | None = None
    peso_kg: float | None = None
    codigo_barras: str | None = None
    lancamento: date | None = None


class Produto(ProdutoCreate, table=True):
    id: UUID = Field(primary_key=True, default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime | None = Field(default=None)
    deleted_at: datetime | None = Field(default=None)


class ProdutoRead(SQLModel):
    id: UUID
    nome: str
    descricao: str | None
    sku: str
    preco: float
    estoque: int
    ativo: bool
    categoria: str
    peso_kg: float | None
    codigo_barras: str | None
    lancamento: date | None
    created_at: datetime
    updated_at: datetime | None
    deleted_at: datetime | None
