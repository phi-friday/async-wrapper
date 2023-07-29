from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, wait
from functools import partial, wraps
from typing import Awaitable, Callable, TypeVar

import anyio
from typing_extensions import ParamSpec

ValueT = TypeVar("ValueT")
ParamT = ParamSpec("ParamT")

__all__ = ["async_to_sync"]


def async_to_sync(
    func: Callable[ParamT, Awaitable[ValueT]],
) -> Callable[ParamT, ValueT]:
    sync_func = _as_sync(func)

    @wraps(func)
    def inner(*args: ParamT.args, **kwargs: ParamT.kwargs) -> ValueT:
        with ThreadPoolExecutor(1) as pool:
            future = pool.submit(sync_func, *args, **kwargs)
            wait([future])
            return future.result()

    return inner


def _as_sync(
    func: Callable[ParamT, Awaitable[ValueT]],
) -> Callable[ParamT, ValueT]:
    @wraps(func)
    def inner(*args: ParamT.args, **kwargs: ParamT.kwargs) -> ValueT:
        return _run(func, *args, **kwargs)

    return inner


def _run(
    func: Callable[ParamT, Awaitable[ValueT]],
    *args: ParamT.args,
    **kwargs: ParamT.kwargs,
) -> ValueT:
    return anyio.run(partial(func, *args, **kwargs))
