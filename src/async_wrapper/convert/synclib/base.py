from __future__ import annotations

from functools import partial, wraps
from typing import Awaitable, Callable, Protocol, TypeVar

import anyio
from typing_extensions import ParamSpec

ValueT = TypeVar("ValueT")
ParamT = ParamSpec("ParamT")

__all__ = ["as_sync_func", "AsyncToSync"]


class AsyncToSync(Protocol):
    def __call__(  # noqa: D102
        self,
        func: Callable[ParamT, Awaitable[ValueT]],
    ) -> Callable[ParamT, ValueT]:
        ...


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
    return anyio.run(partial(func, *args, **kwargs))
