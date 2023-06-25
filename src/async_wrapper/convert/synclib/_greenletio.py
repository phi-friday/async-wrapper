from __future__ import annotations

from typing import Awaitable, Callable, TypeVar

from greenletio import await_
from typing_extensions import ParamSpec

from async_wrapper.convert.synclib.base import as_coro_func

ValueT = TypeVar("ValueT")
ParamT = ParamSpec("ParamT")

__all__ = ["async_to_sync"]


def async_to_sync(
    func: Callable[ParamT, Awaitable[ValueT]],
) -> Callable[ParamT, ValueT]:
    func = as_coro_func(func)
    return await_(func)  # type: ignore
