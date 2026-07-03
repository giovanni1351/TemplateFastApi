"""Sistema RBAC (Role-Based Access Control) por rota.

Como funciona:
- `RBACRouter` é um `APIRouter` que injeta automaticamente a dependência
  `verify_rbac` em todas as rotas registradas nele. Rotas marcadas com o
  decorator `@public_route` ficam de fora da verificação (mas mantêm as
  próprias dependências, como `get_current_user`).
- `verify_rbac` identifica a rota que atendeu a request e verifica se o
  usuário autenticado tem a permissão correspondente. Admins têm bypass.
- `sync_permissions(app)` roda no startup, mapeia todas as rotas protegidas
  e mantém a tabela `Permission` sincronizada (cria novas, atualiza
  metadados e remove rotas que deixaram de existir).
- As permissões são atribuídas a cada usuário pelo painel admin.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any, TypeVar

from auth import get_current_user
from database import AsyncSessionDep, async_engine
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute, APIRouter
from schemas.rbac import (
    GroupPermissionLink,
    Permission,
    UserGroupLink,
    UserPermissionLink,
)
from schemas.user import User
from settings import LOGGER
from sqlalchemy import delete
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

CallableT = TypeVar("CallableT", bound=Callable[..., Any])


def build_permission_code(method: str, path: str) -> str:
    return f"{method.upper()}:{path}"


async def verify_rbac(
    request: Request,
    session: AsyncSessionDep,
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Verifica se o usuário autenticado tem permissão para a rota atual.

    A permissão pode ter sido atribuída diretamente ao usuário ou herdada
    de um grupo de permissões do qual ele faz parte. Admins têm bypass.
    """
    if user.is_admin:
        return user

    route = request.scope.get("route")
    path: str = getattr(route, "path", request.url.path)
    code = build_permission_code(request.method, path)

    direct_stmt = (
        select(UserPermissionLink)
        .join(Permission, col(Permission.id) == col(UserPermissionLink.permission_id))
        .where(
            col(UserPermissionLink.user_id) == user.id,
            col(Permission.code) == code,
        )
    )
    if (await session.exec(direct_stmt)).first() is not None:
        return user

    group_stmt = (
        select(GroupPermissionLink)
        .join(Permission, col(Permission.id) == col(GroupPermissionLink.permission_id))
        .join(
            UserGroupLink,
            col(UserGroupLink.group_id) == col(GroupPermissionLink.group_id),
        )
        .where(
            col(UserGroupLink.user_id) == user.id,
            col(Permission.code) == code,
        )
    )
    if (await session.exec(group_stmt)).first() is not None:
        return user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Você não tem permissão para acessar esta rota",
    )


def public_route(func: CallableT) -> CallableT:
    """Marca o endpoint para NÃO receber a verificação RBAC do RBACRouter."""
    func.__rbac_public__ = True  # pyright: ignore[reportFunctionMemberAccess]
    return func


class RBACRouter(APIRouter):
    """APIRouter que protege todas as rotas com verificação de permissão RBAC.

    Uso:
        router = RBACRouter(prefix="/user", tags=["User"])

        @router.get("/")            # protegida: exige permissão "GET:/user/"
        async def listar(): ...

        @router.post("/")
        @public_route               # fora do RBAC (ex: cadastro, login)
        async def criar(): ...
    """

    def add_api_route(
        self, path: str, endpoint: Callable[..., Any], **kwargs: Any
    ) -> None:
        if not getattr(endpoint, "__rbac_public__", False):
            dependencies = list(kwargs.get("dependencies") or [])
            dependencies.append(Depends(verify_rbac))
            kwargs["dependencies"] = dependencies
        super().add_api_route(path, endpoint, **kwargs)


def _dependant_uses(dependant: Dependant, target: Callable[..., Any]) -> bool:
    """Verifica recursivamente se a árvore de dependências da rota usa `target`."""
    return any(
        dep.call is target or _dependant_uses(dep, target)
        for dep in dependant.dependencies
    )


def _route_description(route: APIRoute) -> str | None:
    if route.summary:
        return route.summary
    first_line = (route.description or "").strip().split("\n")[0].strip()
    return first_line or None


async def sync_permissions(app: FastAPI) -> None:
    """Mapeia todas as rotas protegidas por RBAC e sincroniza a tabela Permission.

    Deve ser chamada no startup da aplicação (lifespan), depois de todos os
    routers já terem sido incluídos.
    """
    LOGGER.info("Sincronizando permissões RBAC com as rotas da aplicação")
    mapped: dict[str, dict[str, str | None]] = {}
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        if not _dependant_uses(route.dependant, verify_rbac):
            continue
        for method in sorted(route.methods or []):
            code = build_permission_code(method, route.path)
            mapped[code] = {
                "method": method,
                "path": route.path,
                "name": route.name,
                "description": _route_description(route),
            }

    async with AsyncSession(async_engine, expire_on_commit=False) as session:
        existing = {
            perm.code: perm for perm in (await session.exec(select(Permission))).all()
        }

        for code, info in mapped.items():
            perm = existing.get(code)
            if perm is None:
                session.add(Permission(code=code, **info))  # pyright: ignore[reportArgumentType]
            elif (perm.name, perm.description) != (info["name"], info["description"]):
                perm.name = info["name"]
                perm.description = info["description"]
                perm.updated_at = datetime.now()
                session.add(perm)

        removed = [perm for code, perm in existing.items() if code not in mapped]
        for perm in removed:
            await session.exec(
                delete(UserPermissionLink).where(  # pyright: ignore[reportArgumentType, reportCallIssue]
                    col(UserPermissionLink.permission_id) == perm.id
                )
            )
            await session.exec(
                delete(GroupPermissionLink).where(  # pyright: ignore[reportArgumentType, reportCallIssue]
                    col(GroupPermissionLink.permission_id) == perm.id
                )
            )
            await session.delete(perm)

        await session.commit()

    LOGGER.info(
        f"Permissões RBAC sincronizadas: {len(mapped)} rotas mapeadas, "
        f"{len(removed)} removidas"
    )


async def get_user_permissions(user: User, session: AsyncSession) -> list[Permission]:
    """Retorna todas as permissões (rotas) que o usuário tem acesso.

    Considera as permissões diretas e as herdadas de grupos.
    Admins têm acesso a todas as rotas mapeadas.
    """
    if user.is_admin:
        result = await session.exec(select(Permission).order_by(col(Permission.code)))
        return list(result.all())

    direct_stmt = (
        select(Permission)
        .join(
            UserPermissionLink,
            col(Permission.id) == col(UserPermissionLink.permission_id),
        )
        .where(col(UserPermissionLink.user_id) == user.id)
    )
    group_stmt = (
        select(Permission)
        .join(
            GroupPermissionLink,
            col(Permission.id) == col(GroupPermissionLink.permission_id),
        )
        .join(
            UserGroupLink,
            col(UserGroupLink.group_id) == col(GroupPermissionLink.group_id),
        )
        .where(col(UserGroupLink.user_id) == user.id)
    )

    permissions = {
        perm.id: perm for perm in (await session.exec(direct_stmt)).all()
    }
    for perm in (await session.exec(group_stmt)).all():
        permissions.setdefault(perm.id, perm)
    return sorted(permissions.values(), key=lambda perm: perm.code)
