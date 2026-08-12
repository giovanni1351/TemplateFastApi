from abc import ABC, abstractmethod
from typing import Any, overload

from fastapi import HTTPException, status
from settings import LOGGER
from sqlalchemy.exc import IntegrityError
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession


class CRUDService[T: SQLModel](ABC):
    def __init__(self, model: type[T], session: AsyncSession) -> None:
        self.model = model
        self.session = session

    @abstractmethod
    async def create(self, *args: list[object], **kwargs: dict[str, object]) -> T:
        pass

    @abstractmethod
    async def read(
        self, *args: list[object], **kwargs: dict[str, object]
    ) -> T | None | list[T]:
        pass

    @abstractmethod
    async def update(self, *args: list[object], **kwargs: dict[str, object]) -> T:
        pass

    @abstractmethod
    async def delete(self, *args: list[object], **kwargs: dict[str, object]) -> T:
        pass

    async def commit(self) -> None:
        await self.session.commit()

    async def get_item_or_404(self, item_id: object) -> T:
        """Helper genérico para buscar"""
        item = await self.session.get(self.model, item_id)
        if not item:
            LOGGER.warning(f"{self.model.__name__} não encontrado")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{self.model.__name__} não encontrado",
            )
        return item


class CRUDGeneric[T: SQLModel](CRUDService[T]):
    async def create(
        self, obj_in: T, *, commit: bool = True, detail_error_message: str | None = None
    ) -> T:
        self.session.add(obj_in)
        if commit:
            try:
                await self.session.commit()
                await self.session.refresh(obj_in)
            except IntegrityError as e:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=detail_error_message or "Ja existe um objeto cadastrado",
                ) from e
        return obj_in

    async def update(
        self,
        data: dict[str, object],
        *,
        old_id: object | None = None,
        primary_key_name: str | None = None,
        commit: bool = True,
    ) -> T:
        if primary_key_name is None:
            primary_key_name = "id"
        print(data.get(primary_key_name))
        if old_id is not None:
            data[primary_key_name] = old_id
        item = await self.get_item_or_404(data.get(primary_key_name))
        del data[primary_key_name]
        for key, value in data.items():
            setattr(item, key, value)
        self.session.add(item)
        if commit:
            await self.session.commit()
            await self.session.refresh(item)
        return item

    @overload
    async def read(self, obj_id: object) -> T: ...
    @overload
    async def read(self) -> list[T]: ...

    async def read(self, obj_id: Any | None = None) -> T | list[T]:
        if not obj_id:
            result = await self.session.exec(select(self.model))
            return list(result.all())

        return await self.get_item_or_404(obj_id)

    async def delete(self, obj_id: object, *, commit: bool = True) -> T:
        item = await self.get_item_or_404(obj_id)
        await self.session.delete(item)
        if commit:
            await self.session.commit()
        return item
