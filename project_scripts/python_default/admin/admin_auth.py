from datetime import timedelta

import jwt
from auth import authenticate_user, create_access_token
from database import get_async_session
from fastapi import HTTPException, Request, status
from schemas.user import User
from settings import SETTINGS
from sqladmin.authentication import AuthenticationBackend
from sqlmodel import select


class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        async for session in get_async_session():
            form = await request.form()
            username, password = form.get("username"), form.get("password")
            if not isinstance(username, str) or not isinstance(password, str):
                return False
            user = await authenticate_user(username, password, session)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Incorrect username or password",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            access_token_expires = timedelta(
                minutes=SETTINGS.ACCESS_TOKEN_EXPIRE_MINUTES
            )

            access_token = create_access_token(
                data={
                    "sub": user.email,
                },
                expires_delta=access_token_expires,
            )

            if access_token:
                request.session.update({"token": access_token})
                return True
        return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        async for session in get_async_session():
            credentials_exception = HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
            token = request.session.get("token")
            if not token:
                return False
            try:
                payload = jwt.decode(  # type: ignore
                    token,
                    SETTINGS.SECRET_KEY,  # type: ignore
                    algorithms=[SETTINGS.ALGORITHM],  # type: ignore
                )
            except jwt.ExpiredSignatureError:
                request.session.clear()
                return False
            email = payload.get("sub")
            # 3. Valida se o token ainda é válido (Bearer Token validation)
            if email is None:
                raise credentials_exception
            user = (await session.exec(select(User).where(User.email == email))).first()
            if not user or not user.is_admin:
                raise credentials_exception
        return True


backend_auth = AdminAuth(SETTINGS.SECRET_KEY)
