from schemas.livro import Livro, LivroRead
from schemas.pagina import Pagina, PaginaRead
from schemas.password_reset import PasswordReset
from schemas.rbac import (
    GroupPermissionLink,
    Permission,
    PermissionGroup,
    UserGroupLink,
    UserPermissionLink,
)
from schemas.user import User, UserCreate

__all__ = [
    "GroupPermissionLink",
    "Livro",
    "Pagina",
    "PasswordReset",
    "Permission",
    "PermissionGroup",
    "User",
    "UserCreate",
    "UserGroupLink",
    "UserPermissionLink",
]

LivroRead.model_rebuild()
PaginaRead.model_rebuild()
