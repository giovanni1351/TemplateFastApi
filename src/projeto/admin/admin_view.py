from typing import Any

from auth import get_password_hash
from schemas.livro import Livro
from schemas.pagina import Pagina
from schemas.password_reset import PasswordReset
from schemas.user import User
from sqladmin import ModelView
from starlette.requests import Request


class UserAdmin(ModelView, model=User):
    column_list = [User.nome, User.sobrenome, User.email, User.is_admin]
    column_details_exclude_list = [User.password]
    can_create = True
    card_style = True
    icon = "fa-solid fa-users"

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
