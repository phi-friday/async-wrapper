from __future__ import annotations

from inspect import iscoroutinefunction
from typing import Any, Callable, Coroutine, TypeVar, overload

from typing_extensions import ParamSpec

from ._async import sync_to_async
from ._sync import async_to_sync

ValueT = TypeVar("ValueT")
ParamT = ParamSpec("ParamT")

__all__ = ["toggle_func", "async_to_sync", "sync_to_async"]


@overload
def toggle_func(  # pyright: ignore[reportOverlappingOverload]
    func: Callable[ParamT, Coroutine[Any, Any, ValueT]],
) -> Callable[ParamT, ValueT]: ...  # pragma: no cover


@overload
def toggle_func(
    func: Callable[ParamT, ValueT],
) -> Callable[ParamT, Coroutine[Any, Any, ValueT]]: ...  # pragma: no cover


def toggle_func(
    func: Callable[ParamT, ValueT] | Callable[ParamT, Coroutine[Any, Any, ValueT]],
) -> Callable[ParamT, ValueT] | Callable[ParamT, Coroutine[Any, Any, ValueT]]:
    """
    Convert between synchronous and asynchronous functions.

    Args:
        func: A function that can be either synchronous or asynchronous.

    Returns:
        A function that matches the desired synchronicity,
        either synchronous or asynchronous.
    """
    if iscoroutinefunction(func):
        return async_to_sync(func)
    return sync_to_async(func)  # type: ignore
