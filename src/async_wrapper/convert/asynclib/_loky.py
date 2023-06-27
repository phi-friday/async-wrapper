from __future__ import annotations

import asyncio
from functools import wraps
from typing import Any, Callable, Coroutine, TypeVar

from typing_extensions import ParamSpec

ValueT = TypeVar("ValueT")
ParamT = ParamSpec("ParamT")

__all__ = ["sync_to_async"]


def sync_to_async(
    func: Callable[ParamT, ValueT],
) -> Callable[ParamT, Coroutine[Any, Any, ValueT]]:
    try:
        from loky.process_executor import (  # type: ignore
            ProcessPoolExecutor,  # type: ignore
        )
    except ImportError as exc:
        raise ImportError("install extas loky first") from exc

    @wraps(func)
    async def inner(*args: ParamT.args, **kwargs: ParamT.kwargs) -> ValueT:
        with ProcessPoolExecutor(1) as pool:
            future = pool.submit(func, *args, **kwargs)  # type: ignore
            coro = asyncio.wrap_future(future)
            return await coro

    return inner
