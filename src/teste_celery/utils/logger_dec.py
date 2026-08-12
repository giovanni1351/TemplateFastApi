from collections.abc import Awaitable, Callable
from functools import wraps

from fastapi import HTTPException, status
from settings import LOGGER


def async_log_and_check_error[**IN, OUT](
    func: Callable[IN, Awaitable[OUT]],
) -> Callable[IN, Awaitable[OUT]]:
    @wraps(func)
    async def wrapper(*args: IN.args, **kwargs: IN.kwargs) -> OUT:
        try:
            LOGGER.debug(f"Executando a função {func.__name__} ")
            result: OUT = await func(*args, **kwargs)
            LOGGER.debug(f"Função {func.__name__} executada com sucesso")
        except HTTPException as e:
            LOGGER.warning(
                f"Erro na função {func.__name__}: {e}",
                extra={
                    "func_name": func.__name__,
                },
            )
            raise e from e
        except Exception as e:
            LOGGER.exception(
                f"Erro na função {func.__name__}: {e}",
                extra={
                    "func_name": func.__name__,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erro na função {func.__name__}: {e}",
            ) from e
        return result

    wrapper.__name__ = func.__name__

    return wrapper


def async_log[**IN, OUT](
    func: Callable[IN, Awaitable[OUT]],
) -> Callable[IN, Awaitable[OUT | None]]:
    @wraps(func)
    async def wrapper(*args: IN.args, **kwargs: IN.kwargs) -> OUT | None:
        result: OUT | None = None
        try:
            LOGGER.debug(
                f"Executando a função {func.__name__} {func.__code__.co_nlocals}"
            )
            if args:
                LOGGER.debug(f"{args=}")
            if kwargs:
                LOGGER.debug(f"{kwargs=}")
            result = await func(*args, **kwargs)
            LOGGER.debug(f"Função {func.__name__} executada com sucesso")
        except Exception as e:  # noqa: BLE001
            LOGGER.exception(
                f"Erro na função {func.__name__}: {e}",
                extra={
                    "func_name": func.__name__,
                },
            )
        return result

    wrapper.__name__ = func.__name__
    return wrapper


def log_and_check_error[**IN, OUT](func: Callable[IN, OUT]) -> Callable[IN, OUT]:
    def wrapper(*args: IN.args, **kwargs: IN.kwargs) -> OUT:
        try:
            LOGGER.debug(f"Executando a função {func.__name__}")
            result = func(*args, **kwargs)
            LOGGER.debug(f"Função {func.__name__} executada com sucesso")
        except Exception as e:
            LOGGER.exception(
                f"Erro na função {func.__name__}: {e}",
                extra={
                    "func_name": func.__name__,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erro na função {func.__name__}: {e}",
            ) from e
        return result

    return wrapper
