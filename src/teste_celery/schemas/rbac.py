from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlmodel import (
    Field,  # type: ignore
    Relationship,
    SQLModel,
)

if TYPE_CHECKING:
    from schemas.user import User


class UserPermissionLink(SQLModel, table=True):
    user_id: UUID = Field(foreign_key="user.id", primary_key=True)
    permission_id: UUID = Field(foreign_key="permission.id", primary_key=True)


class UserGroupLink(SQLModel, table=True):
    user_id: UUID = Field(foreign_key="user.id", primary_key=True)
    group_id: UUID = Field(foreign_key="permissiongroup.id", primary_key=True)


class GroupPermissionLink(SQLModel, table=True):
    group_id: UUID = Field(foreign_key="permissiongroup.id", primary_key=True)
    permission_id: UUID = Field(foreign_key="permission.id", primary_key=True)


class Permission(SQLModel, table=True):
    id: UUID = Field(primary_key=True, default_factory=uuid4)
    code: str = Field(unique=True, index=True)  # ex: "GET:/user/"
    method: str
    path: str
    name: str | None = Field(default=None)
    description: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime | None = Field(default=None)
    users: list["User"] = Relationship(  # pyright: ignore[reportUnknownVariableType]
        back_populates="permissions", link_model=UserPermissionLink
    )
    groups: list["PermissionGroup"] = Relationship(  # pyright: ignore[reportUnknownVariableType]
        back_populates="permissions", link_model=GroupPermissionLink
    )

    def __str__(self) -> str:
        return f"{self.method} {self.path}"


class PermissionGroup(SQLModel, table=True):
    """Grupo de permissões (role). Usuários herdam as permissões dos grupos."""

    id: UUID = Field(primary_key=True, default_factory=uuid4)
    name: str = Field(unique=True, index=True)
    description: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime | None = Field(default=None)
    permissions: list[Permission] = Relationship(  # pyright: ignore[reportUnknownVariableType]
        back_populates="groups", link_model=GroupPermissionLink
    )
    users: list["User"] = Relationship(  # pyright: ignore[reportUnknownVariableType]
        back_populates="groups", link_model=UserGroupLink
    )

    def __str__(self) -> str:
        return self.name


class PermissionRead(SQLModel):
    code: str
    method: str
    path: str
    name: str | None
    description: str | None
