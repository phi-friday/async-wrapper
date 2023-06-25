from __future__ import annotations

import asyncio
from functools import wraps
from typing import Any, Awaitable, Callable, Coroutine, Protocol, TypeVar

from typing_extensions import ParamSpec

ValueT = TypeVar("ValueT")
ParamT = ParamSpec("ParamT")

__all__ = ["as_coro_func", "as_sync_func", "AsyncToSync"]


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


def as_sync_func(
    func: Callable[ParamT, Awaitable[ValueT]],
) -> Callable[ParamT, ValueT]:
    """awaitable func to sync func

    Args:
        func: awaitable func

    Returns:
        sync func
    """

    @wraps(func)
    def inner(*args: ParamT.args, **kwargs: ParamT.kwargs) -> ValueT:
        return run_awaitable_func(func, *args, **kwargs)

    return inner


def run_awaitable_func(
    func: Callable[ParamT, Awaitable[ValueT]],
    *args: ParamT.args,
    **kwargs: ParamT.kwargs,
) -> ValueT:
    """run awaitable func

    Args:
        func: awaitable func

    Returns:
        func result
    """
    func = as_coro_func(func)
    return asyncio.run(func(*args, **kwargs))
