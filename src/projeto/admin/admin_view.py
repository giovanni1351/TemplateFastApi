from typing import Any

from auth import get_password_hash
from schemas.livro import Livro
from schemas.pagina import Pagina
from schemas.password_reset import PasswordReset
from schemas.rbac import Permission, PermissionGroup
from schemas.user import User
from sqladmin import ModelView
from starlette.requests import Request


class UserAdmin(ModelView, model=User):
    column_list = [User.nome, User.sobrenome, User.email, User.is_admin]
    column_details_exclude_list = [User.password]
    can_create = True
    card_style = True
    icon = "fa-solid fa-users"
    # permissões e grupos são gerenciados pela tela "Gerenciar Acessos"
    form_excluded_columns = [User.permissions, User.groups]  # noqa: RUF012

    async def insert_model(self, request: Request, data: dict[str, Any]) -> User:
        if data.get("password"):
            data["password"] = get_password_hash(data["password"])
        return await super().insert_model(request, data)

    async def update_model(
        self, request: Request, pk: Any, data: dict[str, Any]
    ) -> User:
        if "password" in data:
            if data["password"]:
                data["password"] = get_password_hash(data["password"])
            else:
                data.pop("password")
        return await super().update_model(request, pk, data)


class PasswordResetAdmin(ModelView, model=PasswordReset):
    card_style = False
    icon = "🔑"


class LivroAdmin(ModelView, model=Livro):
    column_list = [Livro.nome]
    card_style = True
    icon = "/static/icons/book.svg"


class PaginaAdmin(ModelView, model=Pagina):
    column_list = [Pagina.nome, Pagina.numero]
    card_style = False
    icon = None


class PermissionAdmin(ModelView, model=Permission):
    """Rotas mapeadas automaticamente pelo RBAC.

    A criação/remoção é feita pelo sync no startup da aplicação; aqui o
    admin só atribui as permissões aos usuários.
    """

    name = "Permissão"
    name_plural = "Permissões"
    column_list = [
        Permission.method,
        Permission.path,
        Permission.name,
        Permission.description,
    ]
    column_searchable_list = [Permission.code, Permission.path, Permission.name]
    column_sortable_list = [Permission.method, Permission.path, Permission.name]
    form_columns = ["description"]  # noqa: RUF012
    can_create = False
    can_delete = False
    card_style = False
    icon = "fa-solid fa-shield-halved"


class PermissionGroupAdmin(ModelView, model=PermissionGroup):
    """Grupos de permissões (roles).

    A atribuição de rotas e usuários é feita na tela "Gerenciar Acessos".
    """

    name = "Grupo de Permissões"
    name_plural = "Grupos de Permissões"
    column_list = [PermissionGroup.name, PermissionGroup.description]
    column_searchable_list = [PermissionGroup.name, PermissionGroup.description]
    column_sortable_list = [PermissionGroup.name]
    form_columns = ["name", "description"]  # noqa: RUF012
    card_style = False
    icon = "fa-solid fa-user-shield"


from schemas.produto import Produto  # noqa: E402


class ProdutoAdmin(ModelView, model=Produto):
    column_list = [Produto.nome, Produto.descricao, Produto.sku, Produto.preco, Produto.estoque]  # noqa: RUF012
    card_style = False
    icon = None
