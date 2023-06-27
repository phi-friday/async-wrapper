from __future__ import annotations

from inspect import iscoroutinefunction
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Coroutine,
    TypeVar,
    overload,
)

from typing_extensions import ParamSpec

from async_wrapper.convert.asynclib import get_async_convertor
from async_wrapper.convert.synclib import get_sync_convertor

if TYPE_CHECKING:
    from async_wrapper.convert.asynclib.main import AsyncBackendType
    from async_wrapper.convert.synclib.main import SyncBackendType

ValueT = TypeVar("ValueT")
ParamT = ParamSpec("ParamT")

__all__ = ["toggle_func", "async_to_sync", "sync_to_async"]


@overload
def toggle_func(
    func: Callable[ParamT, Coroutine[Any, Any, ValueT]],
    *,
    backend: SyncBackendType | None = None,
) -> Callable[ParamT, ValueT]:
    ...


@overload
def toggle_func(
    func: Callable[ParamT, ValueT],
    *,
    backend: AsyncBackendType | None = None,
) -> Callable[ParamT, Coroutine[Any, Any, ValueT]]:
    ...


def toggle_func(
    func: Callable[ParamT, ValueT] | Callable[ParamT, Coroutine[Any, Any, ValueT]],
    *,
    backend: SyncBackendType | AsyncBackendType | None = None,
) -> Callable[ParamT, ValueT] | Callable[ParamT, Coroutine[Any, Any, ValueT]]:
    """sync to async, async to sync

    Args:
        func: sync or async func
        backend: sync or async backend. Defaults to None.

    Returns:
        async or sync func
    """
    if iscoroutinefunction(func):
        convertor = get_sync_convertor(backend)
        return convertor(func)  # type: ignore

    convertor = get_async_convertor(backend)  # type: ignore
    return convertor(func)  # type: ignore


async_to_sync = get_sync_convertor
sync_to_async = get_async_convertor
