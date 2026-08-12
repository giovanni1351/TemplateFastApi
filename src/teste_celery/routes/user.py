from datetime import datetime, timedelta
from typing import Annotated
from uuid import UUID, uuid4

from auth import get_current_user, get_password_hash
from database import AsyncSessionDep
from fastapi import Depends, HTTPException, status
from schemas.password_reset import (
    ForgotPasswordRequest,
    PasswordReset,
    ResetPasswordRequest,
)

from schemas.rbac import PermissionRead
from schemas.user import (
    User,
    UserCreate,
    UserUpdate,
)
from settings import SETTINGS
from sqlmodel import col, select
from utils.crud import CRUDGeneric
from utils.email_service import send_password_reset_email

from utils.rbac_router import RBACRouter, get_user_permissions, public_route

router = RBACRouter(prefix="/user", tags=["User"])


@router.post("/")
@public_route  # cadastro é aberto
async def post_user(user: UserCreate, session: AsyncSessionDep) -> UserCreate:
    user_new = User(**user.model_dump())
    user_new.password = get_password_hash(user.password)
    crud = CRUDGeneric(User, session)
    await crud.create(user_new, detail_error_message="Usuario com o nome ja cadastrado")
    return user_new


@router.put("/")
@public_route  # usuário autenticado sempre pode atualizar o próprio cadastro
async def put_user(
    user: UserUpdate,
    session: AsyncSessionDep,
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    crud = CRUDGeneric(User, session)

    return await crud.update(user.model_dump(), old_id=current_user.id)


@router.get("/")
async def get_users(
    session: AsyncSessionDep,
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[User]:
    # protegida: admin ou usuário com permissão
    crud = CRUDGeneric(User, session)
    return await crud.read()


@router.delete("/")
@public_route  # usuário autenticado sempre pode deletar a própria conta
async def delete_user(
    session: AsyncSessionDep,
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    crud = CRUDGeneric(User, session)
    return await crud.delete(current_user.id)


@router.delete("/{user_id}")
async def delete_user_by_id(
    user_id: UUID,
    session: AsyncSessionDep,
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    # protegida: admin ou usuário com permissão
    crud = CRUDGeneric(User, session)
    return await crud.delete(user_id)


@router.get("/me")
@public_route  # usuário autenticado sempre pode ver o próprio cadastro
async def get_me(
    session: AsyncSessionDep,
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    return current_user


@router.get("/me/permissions")
@public_route  # usuário autenticado sempre pode consultar as próprias permissões
async def get_my_permissions(
    session: AsyncSessionDep,
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[PermissionRead]:
    """Retorna todas as rotas que o usuário atual tem acesso."""
    permissions = await get_user_permissions(current_user, session)
    return [PermissionRead.model_validate(p) for p in permissions]


@router.get("/{user_id}")
async def get_user_by_id(
    user_id: UUID,
    session: AsyncSessionDep,
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    # protegida: admin ou usuário com permissão
    crud = CRUDGeneric(User, session)
    return await crud.read(user_id)


@router.post("/forgot-password")
@public_route  # fluxo de recuperação de senha é aberto
async def forgot_password(
    data: ForgotPasswordRequest, session: AsyncSessionDep
) -> dict[str, str]:
    """
    Inicia o fluxo de recuperação de senha.
    Envia um email com um token para redefinir a senha.
    """
    result = await session.exec(select(User).where(col(User.email) == data.email))
    user = result.first()

    # Por segurança, sempre retornamos sucesso mesmo se o usuário não existir
    if not user:
        return {"message": "Se o email existir, um link de recuperação será enviado"}

    # Gera token
    token = str(uuid4())
    expires_at = datetime.now() + timedelta(hours=1)

    # Remove tokens antigos não usados deste email
    tokens_antigos = await session.exec(
        select(PasswordReset).where(PasswordReset.email == data.email)
    )
    for t in tokens_antigos.all():
        await session.delete(t)

    # Cria novo registro
    reset_entry = PasswordReset(
        email=data.email,
        token=token,
        expires_at=expires_at,
    )
    session.add(reset_entry)
    await session.commit()

    link = f"{SETTINGS.FRONTEND_PUBLIC_URL}/reset-password?token={token}"
    send_password_reset_email(data.email, link)

    return {"message": "Se o email existir, um link de recuperação será enviado"}


@router.post("/reset-password")
@public_route  # fluxo de recuperação de senha é aberto
async def reset_password(
    data: ResetPasswordRequest, session: AsyncSessionDep
) -> dict[str, str]:
    """
    Redefine a senha usando um token válido.
    """
    result = await session.exec(
        select(PasswordReset).where(
            PasswordReset.token == data.token,
            PasswordReset.used_at == None,  # noqa: E711
            PasswordReset.expires_at > datetime.now(),
        )
    )
    reset_entry = result.first()

    if not reset_entry:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token inválido ou expirado",
        )

    user_result = await session.exec(
        select(User).where(User.email == reset_entry.email)
    )
    user = user_result.first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário associado ao token não encontrado",
        )

    user.password = get_password_hash(data.new_password)
    session.add(user)

    reset_entry.used_at = datetime.now()
    session.add(reset_entry)

    await session.commit()

    return {"message": "Senha redefinida com sucesso"}
