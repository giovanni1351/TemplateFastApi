from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from schemas.rbac import UserGroupLink, UserPermissionLink
from sqlmodel import (
    Field,  # pyright: ignore[reportUnknownVariableType]
    Relationship,
    SQLModel,
)

if TYPE_CHECKING:
    from schemas.rbac import Permission, PermissionGroup


class UserTypes(Enum):
    ASSINANTE = "ASSINANTE"
    ASSINANTE_PLUS = "ASSINANTE_PLUS"
    COMUM = "COMUM"


class UserCreate(SQLModel):
    nome: str
    sobrenome: str
    email: str = Field(default="sem_email@gmail.com", unique=True)
    password: str


class UserUpdate(SQLModel):
    nome: str | None = None
    sobrenome: str | None = None


class User(UserCreate, table=True):
    id: UUID = Field(primary_key=True, default_factory=uuid4)
    is_admin: bool = Field(default=False)
    user_type: UserTypes = UserTypes.COMUM
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime | None = Field(default=None)
    deleted_at: datetime | None = Field(default=None)
    permissions: list["Permission"] = Relationship(  # pyright: ignore[reportUnknownVariableType]
        back_populates="users", link_model=UserPermissionLink
    )
    groups: list["PermissionGroup"] = Relationship(  # pyright: ignore[reportUnknownVariableType]
        back_populates="users", link_model=UserGroupLink
    )
