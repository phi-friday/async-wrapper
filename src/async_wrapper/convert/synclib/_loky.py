from __future__ import annotations

from concurrent.futures import wait
from functools import wraps
from typing import Awaitable, Callable, TypeVar

from typing_extensions import ParamSpec

from async_wrapper.convert.synclib.base import as_sync_func

ValueT = TypeVar("ValueT")
ParamT = ParamSpec("ParamT")

__all__ = ["async_to_sync"]


def async_to_sync(
    func: Callable[ParamT, Awaitable[ValueT]],
) -> Callable[ParamT, ValueT]:
    try:
        from loky.process_executor import (  # type: ignore
            ProcessPoolExecutor,  # type: ignore
        )
    except ImportError as exc:
        raise ImportError("install extas loky first") from exc

    sync_func = as_sync_func(func)

    @wraps(func)
    def inner(*args: ParamT.args, **kwargs: ParamT.kwargs) -> ValueT:
        with ProcessPoolExecutor(1) as pool:
            future = pool.submit(sync_func, *args, **kwargs)  # type: ignore
            wait([future])
            return future.result()

    return inner
