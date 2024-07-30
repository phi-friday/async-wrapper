from __future__ import annotations

from inspect import iscoroutinefunction
from typing import TYPE_CHECKING, Any, Callable, overload

from typing_extensions import ParamSpec, TypeVar

from async_wrapper.convert._async import sync_to_async
from async_wrapper.convert._sync import async_to_sync

if TYPE_CHECKING:
    from collections.abc import Coroutine

ValueT = TypeVar("ValueT", infer_variance=True)
ParamT = ParamSpec("ParamT")

__all__ = ["toggle_func", "async_to_sync", "sync_to_async"]


@overload
def toggle_func(
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
