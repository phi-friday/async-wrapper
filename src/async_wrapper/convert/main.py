from __future__ import annotations

from inspect import iscoroutinefunction
from typing import TYPE_CHECKING, Any, overload

from typing_extensions import ParamSpec, TypeAlias, TypeVar

from async_wrapper.convert._async import Async, sync_to_async
from async_wrapper.convert._sync import async_to_sync
from async_wrapper.convert._sync.main import Sync

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Coroutine

ValueT = TypeVar("ValueT", infer_variance=True)
ParamT = ParamSpec("ParamT")
AnyAwaitable: TypeAlias = "Awaitable[ValueT] | Coroutine[Any, Any, ValueT]"

__all__ = ["toggle_func", "async_to_sync", "sync_to_async"]


@overload
def toggle_func(
    func: Callable[ParamT, Coroutine[Any, Any, ValueT]],
) -> Callable[ParamT, ValueT]: ...  # pragma: no cover


@overload
def toggle_func(
    func: Callable[ParamT, ValueT],
) -> Callable[ParamT, AnyAwaitable[ValueT]]: ...  # pragma: no cover


# TODO: Coroutine -> AnyAwaitable
def toggle_func(
    func: Callable[ParamT, ValueT] | Callable[ParamT, Coroutine[Any, Any, ValueT]],
) -> Callable[ParamT, ValueT] | Callable[ParamT, AnyAwaitable[ValueT]]:
    """
    Convert between synchronous and asynchronous functions.

    Args:
        func: A function that can be either synchronous or asynchronous.

    Returns:
        A function that matches the desired synchronicity,
        either synchronous or asynchronous.
    """
    if isinstance(func, (Async, Sync)):
        return func._func  # pyright: ignore[reportReturnType]  # noqa: SLF001
    if iscoroutinefunction(func):
        return async_to_sync(func)
    return sync_to_async(func)  # pyright: ignore[reportReturnType]
