from typing import Annotated

from auth import get_current_user, get_password_hash
from database import AsyncSessionDep
from fastapi import APIRouter, Depends, HTTPException, status
from schemas.user import User, UserCreate
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

router = APIRouter(prefix="/user")


@router.post("/")
async def post_user(user: UserCreate, session: AsyncSessionDep) -> UserCreate:
    user_new = User(**user.model_dump())
    user_new.password = get_password_hash(user.password)
    try:
        session.add(user_new)
        await session.commit()
        await session.refresh(user_new)
    except IntegrityError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Usuario com o nome ja cadastrado",
        ) from e
    return user_new


@router.get("/")
async def get_user(
    session: AsyncSessionDep, current_user: Annotated[User, Depends(get_current_user)]
) -> list[User]:
    return list((await session.exec(select(User))).fetchall())
