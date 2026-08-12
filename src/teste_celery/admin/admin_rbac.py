"""Tela de gerenciamento de acessos (RBAC) no admin.

Permite criar/editar grupos de permissões escolhendo as rotas mapeadas e os
usuários membros, e gerenciar por usuário os grupos e permissões diretas.
"""

from uuid import UUID

from database import async_engine
from schemas.rbac import (
    GroupPermissionLink,
    Permission,
    PermissionGroup,
    UserGroupLink,
    UserPermissionLink,
)
from schemas.user import User
from sqladmin import BaseView, expose
from sqlalchemy import delete
from sqlalchemy.orm import selectinload
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from utils.rbac_router import get_user_permissions


def _parse_uuid(value: str) -> UUID | None:
    try:
        return UUID(value)
    except (ValueError, AttributeError, TypeError):
        return None


def _grouped_permissions(
    permissions: list[Permission],
) -> dict[str, list[Permission]]:
    """Agrupa as permissões pelo primeiro segmento do path (ex: /user/... -> user)."""
    grouped: dict[str, list[Permission]] = {}
    for perm in sorted(permissions, key=lambda p: (p.path, p.method)):
        section = perm.path.strip("/").split("/")[0] or "raiz"
        grouped.setdefault(section, []).append(perm)
    return grouped


class RBACAdmin(BaseView):
    name = "Gerenciar Acessos"
    icon = "fa-solid fa-key"

    @expose("/rbac", methods=["GET"], identity="rbac-acessos")
    async def acessos_index(self, request: Request) -> Response:
        async with AsyncSession(async_engine, expire_on_commit=False) as session:
            groups = (
                await session.exec(
                    select(PermissionGroup)
                    .options(
                        selectinload(PermissionGroup.permissions),  # pyright: ignore[reportArgumentType]
                        selectinload(PermissionGroup.users),  # pyright: ignore[reportArgumentType]
                    )
                    .order_by(col(PermissionGroup.name))
                )
            ).all()
            users = (
                await session.exec(
                    select(User)
                    .options(
                        selectinload(User.permissions),  # pyright: ignore[reportArgumentType]
                        selectinload(User.groups),  # pyright: ignore[reportArgumentType]
                    )
                    .order_by(col(User.nome))
                )
            ).all()
            permissions = (await session.exec(select(Permission))).all()

        return await self.templates.TemplateResponse(
            request,
            "sqladmin/rbac_index.html",
            {
                "title": "Gerenciar Acessos",
                "subtitle": "Grupos de permissões e acessos por usuário",
                "groups": groups,
                "users": users,
                "total_permissions": len(permissions),
                "saved": request.query_params.get("saved"),
            },
        )

    @expose("/rbac/grupo/novo", methods=["GET", "POST"], identity="rbac-grupo-novo")
    async def grupo_novo(self, request: Request) -> Response:
        return await self._grupo_form(request, group_id=None)

    @expose("/rbac/grupo/{pk}", methods=["GET", "POST"], identity="rbac-grupo")
    async def grupo_editar(self, request: Request) -> Response:
        group_id = _parse_uuid(request.path_params["pk"])
        if group_id is None:
            return RedirectResponse(
                request.url_for("admin:rbac-acessos"), status_code=303
            )
        return await self._grupo_form(request, group_id=group_id)

    @expose("/rbac/grupo/{pk}/excluir", methods=["POST"], identity="rbac-grupo-excluir")
    async def grupo_excluir(self, request: Request) -> Response:
        group_id = _parse_uuid(request.path_params["pk"])
        if group_id is not None:
            async with AsyncSession(async_engine, expire_on_commit=False) as session:
                group = await session.get(PermissionGroup, group_id)
                if group is not None:
                    await session.exec(
                        delete(GroupPermissionLink).where(  # pyright: ignore[reportArgumentType, reportCallIssue]
                            col(GroupPermissionLink.group_id) == group_id
                        )
                    )
                    await session.exec(
                        delete(UserGroupLink).where(  # pyright: ignore[reportArgumentType, reportCallIssue]
                            col(UserGroupLink.group_id) == group_id
                        )
                    )
                    await session.delete(group)
                    await session.commit()
        return RedirectResponse(
            str(request.url_for("admin:rbac-acessos")) + "?saved=1", status_code=303
        )

    @expose("/rbac/usuario/{pk}", methods=["GET", "POST"], identity="rbac-usuario")
    async def usuario_editar(self, request: Request) -> Response:
        user_id = _parse_uuid(request.path_params["pk"])
        if user_id is None:
            return RedirectResponse(
                request.url_for("admin:rbac-acessos"), status_code=303
            )

        async with AsyncSession(async_engine, expire_on_commit=False) as session:
            user = await session.get(User, user_id)
            if user is None:
                return RedirectResponse(
                    request.url_for("admin:rbac-acessos"), status_code=303
                )

            if request.method == "POST":
                form = await request.form()
                perm_ids = [
                    pid
                    for raw in form.getlist("permissions")
                    if (pid := _parse_uuid(str(raw))) is not None
                ]
                group_ids = [
                    gid
                    for raw in form.getlist("groups")
                    if (gid := _parse_uuid(str(raw))) is not None
                ]
                await session.exec(
                    delete(UserPermissionLink).where(  # pyright: ignore[reportArgumentType, reportCallIssue]
                        col(UserPermissionLink.user_id) == user_id
                    )
                )
                await session.exec(
                    delete(UserGroupLink).where(  # pyright: ignore[reportArgumentType, reportCallIssue]
                        col(UserGroupLink.user_id) == user_id
                    )
                )
                for pid in perm_ids:
                    session.add(
                        UserPermissionLink(user_id=user_id, permission_id=pid)
                    )
                for gid in group_ids:
                    session.add(UserGroupLink(user_id=user_id, group_id=gid))
                await session.commit()
                return RedirectResponse(
                    str(request.url_for("admin:rbac-acessos")) + "?saved=1",
                    status_code=303,
                )

            permissions = (await session.exec(select(Permission))).all()
            groups = (
                await session.exec(
                    select(PermissionGroup)
                    .options(selectinload(PermissionGroup.permissions))  # pyright: ignore[reportArgumentType]
                    .order_by(col(PermissionGroup.name))
                )
            ).all()
            direct_ids = {
                link.permission_id
                for link in (
                    await session.exec(
                        select(UserPermissionLink).where(
                            col(UserPermissionLink.user_id) == user_id
                        )
                    )
                ).all()
            }
            group_ids = {
                link.group_id
                for link in (
                    await session.exec(
                        select(UserGroupLink).where(
                            col(UserGroupLink.user_id) == user_id
                        )
                    )
                ).all()
            }
            effective = await get_user_permissions(user, session)

        return await self.templates.TemplateResponse(
            request,
            "sqladmin/rbac_usuario.html",
            {
                "title": f"Acessos de {user.nome} {user.sobrenome}",
                "subtitle": user.email,
                "user": user,
                "grouped_permissions": _grouped_permissions(list(permissions)),
                "groups": groups,
                "direct_ids": direct_ids,
                "group_ids": group_ids,
                "effective": effective,
            },
        )

    async def _grupo_form(self, request: Request, group_id: UUID | None) -> Response:
        async with AsyncSession(async_engine, expire_on_commit=False) as session:
            group: PermissionGroup | None = None
            if group_id is not None:
                group = await session.get(PermissionGroup, group_id)
                if group is None:
                    return RedirectResponse(
                        request.url_for("admin:rbac-acessos"), status_code=303
                    )

            error: str | None = None
            form_name = group.name if group else ""
            form_description = (group.description if group else "") or ""

            if request.method == "POST":
                form = await request.form()
                form_name = str(form.get("name", "")).strip()
                form_description = str(form.get("description", "")).strip()
                perm_ids = [
                    pid
                    for raw in form.getlist("permissions")
                    if (pid := _parse_uuid(str(raw))) is not None
                ]
                user_ids = [
                    uid
                    for raw in form.getlist("users")
                    if (uid := _parse_uuid(str(raw))) is not None
                ]

                if not form_name:
                    error = "O nome do grupo é obrigatório"
                else:
                    stmt = select(PermissionGroup).where(
                        col(PermissionGroup.name) == form_name
                    )
                    if group is not None:
                        stmt = stmt.where(col(PermissionGroup.id) != group.id)
                    if (await session.exec(stmt)).first() is not None:
                        error = f'Já existe um grupo chamado "{form_name}"'

                if error is None:
                    if group is None:
                        group = PermissionGroup(
                            name=form_name, description=form_description or None
                        )
                        session.add(group)
                        await session.flush()
                    else:
                        group.name = form_name
                        group.description = form_description or None
                        session.add(group)
                        await session.exec(
                            delete(GroupPermissionLink).where(  # pyright: ignore[reportArgumentType, reportCallIssue]
                                col(GroupPermissionLink.group_id) == group.id
                            )
                        )
                        await session.exec(
                            delete(UserGroupLink).where(  # pyright: ignore[reportArgumentType, reportCallIssue]
                                col(UserGroupLink.group_id) == group.id
                            )
                        )
                    for pid in perm_ids:
                        session.add(
                            GroupPermissionLink(group_id=group.id, permission_id=pid)
                        )
                    for uid in user_ids:
                        session.add(UserGroupLink(user_id=uid, group_id=group.id))
                    await session.commit()
                    return RedirectResponse(
                        str(request.url_for("admin:rbac-acessos")) + "?saved=1",
                        status_code=303,
                    )

                # em caso de erro, mantém as seleções feitas no formulário
                selected_perm_ids = set(perm_ids)
                selected_user_ids = set(user_ids)
            elif group is not None:
                selected_perm_ids = {
                    link.permission_id
                    for link in (
                        await session.exec(
                            select(GroupPermissionLink).where(
                                col(GroupPermissionLink.group_id) == group.id
                            )
                        )
                    ).all()
                }
                selected_user_ids = {
                    link.user_id
                    for link in (
                        await session.exec(
                            select(UserGroupLink).where(
                                col(UserGroupLink.group_id) == group.id
                            )
                        )
                    ).all()
                }
            else:
                selected_perm_ids = set()
                selected_user_ids = set()

            permissions = (await session.exec(select(Permission))).all()
            users = (
                await session.exec(select(User).order_by(col(User.nome)))
            ).all()

        return await self.templates.TemplateResponse(
            request,
            "sqladmin/rbac_grupo.html",
            {
                "title": f"Grupo: {group.name}" if group else "Novo Grupo",
                "subtitle": "Selecione as rotas e os usuários do grupo",
                "group": group,
                "error": error,
                "form_name": form_name,
                "form_description": form_description,
                "grouped_permissions": _grouped_permissions(list(permissions)),
                "users": users,
                "selected_perm_ids": selected_perm_ids,
                "selected_user_ids": selected_user_ids,
            },
        )
