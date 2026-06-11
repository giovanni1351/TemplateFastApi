from datetime import datetime, timedelta
from typing import Annotated
from uuid import UUID, uuid4

from auth import UserByRole, get_current_user, get_password_hash
from database import AsyncSessionDep
from fastapi import APIRouter, Depends, HTTPException, status
from schemas.password_reset import (
    ForgotPasswordRequest,
    PasswordReset,
    ResetPasswordRequest,
)
from schemas.user import (
    User,
    UserCreate,
    UserUpdate,
)
from settings import SETTINGS
from sqlmodel import col, select
from utils.crud import CRUDGeneric
from utils.email_service import send_password_reset_email

router = APIRouter(prefix="/user", tags=["User"])


@router.post("/")
async def post_user(user: UserCreate, session: AsyncSessionDep) -> UserCreate:
    user_new = User(**user.model_dump())
    user_new.password = get_password_hash(user.password)
    crud = CRUDGeneric(User, session)
    await crud.create(user_new, detail_error_message="Usuario com o nome ja cadastrado")
    return user_new


@router.put("/")
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
    current_user: Annotated[
        User, Depends(UserByRole([]))
    ],  # somente admin pode listar outros usuarios
) -> list[User]:
    crud = CRUDGeneric(User, session)
    return await crud.read()


@router.delete("/")
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
    current_user: Annotated[
        User, Depends(UserByRole([]))
    ],  # somente admin pode deletar outros usuarios
) -> User:
    crud = CRUDGeneric(User, session)
    return await crud.delete(user_id)


@router.get("/me")
async def get_me(
    session: AsyncSessionDep,
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    return current_user


@router.get("/{user_id}")
async def get_user_by_id(
    user_id: UUID,
    session: AsyncSessionDep,
    current_user: Annotated[
        User, Depends(UserByRole([]))
    ],  # somente admin pode ver outros usuarios
) -> User:
    crud = CRUDGeneric(User, session)
    return await crud.read(user_id)


@router.post("/forgot-password")
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

    # Envia email (LINK HARDCODED PARA LOCALHOST/FRONTEND POR ENQUANTO)
    # No futuro, pegar base_url de settings
    link = f"{SETTINGS.FRONTEND_PUBLIC_URL}/reset-password?token={token}"
    send_password_reset_email(data.email, link)

    return {"message": "Se o email existir, um link de recuperação será enviado"}


@router.post("/reset-password")
async def reset_password(
    data: ResetPasswordRequest, session: AsyncSessionDep
) -> dict[str, str]:
    """
    Redefine a senha usando um token válido.
    """
    # Busca token
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

    # Busca usuário
    user_result = await session.exec(
        select(User).where(User.email == reset_entry.email)
    )
    user = user_result.first()

    if not user:
        # Isso seria estranho (token existe mas usuário não), mas tratamos
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário associado ao token não encontrado",
        )

    # Atualiza senha
    user.password = get_password_hash(data.new_password)
    session.add(user)

    # Marca token como usado
    reset_entry.used_at = datetime.now()
    session.add(reset_entry)

    await session.commit()

    return {"message": "Senha redefinida com sucesso"}
