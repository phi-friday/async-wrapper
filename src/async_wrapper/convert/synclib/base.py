from __future__ import annotations

from functools import wraps
from typing import Any, Awaitable, Callable, Coroutine, Protocol, TypeVar

from typing_extensions import ParamSpec

ValueT = TypeVar("ValueT")
ParamT = ParamSpec("ParamT")

__all__ = ["as_coro_func", "AsyncToSync"]


class AsyncToSync(Protocol):
    def __call__(  # noqa: D102
        self,
        func: Callable[ParamT, Awaitable[ValueT]],
    ) -> Callable[ParamT, ValueT]:
        ...


def as_coro_func(
    func: Callable[ParamT, Awaitable[ValueT]],
) -> Callable[ParamT, Coroutine[Any, Any, ValueT]]:
    """awaitable func to corotine func

    Args:
        func: awaitable func

    Returns:
        corotine func
    """

    @wraps(func)
    async def inner(*args: ParamT.args, **kwargs: ParamT.kwargs) -> ValueT:
        return await func(*args, **kwargs)

    return inner
