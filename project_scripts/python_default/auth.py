from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal

import jwt
from database import AsyncSessionDep
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt import InvalidTokenError
from pwdlib import PasswordHash
from schemas.token import TokenData
from schemas.user import User, UserTypes
from settings import LOGGER, SETTINGS
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

LOGGER.info("sCriando o sistema de autenticação")
SECRET_KEY = SETTINGS.SECRET_KEY
ALGORITHM = SETTINGS.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = SETTINGS.ACCESS_TOKEN_EXPIRE_MINUTES

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
pwd_context = PasswordHash.recommended()
LOGGER.info("Sistema de autenticação criado com sucesso")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)], session: AsyncSessionDep
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(  # type: ignore
            token,
            SETTINGS.SECRET_KEY,  # type: ignore
            algorithms=[SETTINGS.ALGORITHM],  # type: ignore
        )
        email = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except InvalidTokenError as e:
        raise credentials_exception from e
    user = (
        await session.exec(select(User).where(User.email == token_data.email))
    ).first()
    if user is None:
        raise credentials_exception
    return user


class UserByRole:
    def __init__(self, roles: list[UserTypes]) -> None:
        self.roles: list[UserTypes] = roles

    def __call__(self, user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.is_admin:
            return user
        if user.user_type in self.roles:
            return user

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Você não tem acesso a este recurso",
        )


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str | bytes) -> str:
    return pwd_context.hash(password)


async def authenticate_user(
    username: str, password: str, session: AsyncSession
) -> User | Literal[False]:
    LOGGER.info(f"Autenticando usuário {username}")
    user = (await session.exec(select(User).where(User.email == username))).first()
    if not user:
        return False
    if not verify_password(password, user.password):
        return False
    return user


def create_access_token(
    data: dict[str, Any], expires_delta: timedelta | None = None
) -> str:
    LOGGER.info("Criando token de acesso")
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=15)
    to_encode.update({"exp": expire})  # type: ignore
    return jwt.encode(to_encode, SETTINGS.SECRET_KEY, algorithm=SETTINGS.ALGORITHM)  # type: ignore
