from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import wraps
from typing import Any, Callable, Coroutine, TypeVar

from typing_extensions import ParamSpec

ValueT = TypeVar("ValueT")
ParamT = ParamSpec("ParamT")

__all__ = ["sync_to_async"]


def sync_to_async(
    func: Callable[ParamT, ValueT],
) -> Callable[ParamT, Coroutine[Any, Any, ValueT]]:
    @wraps(func)
    async def inner(*args: ParamT.args, **kwargs: ParamT.kwargs) -> ValueT:
        with ThreadPoolExecutor(1) as pool:
            future = pool.submit(func, *args, **kwargs)
            coro = asyncio.wrap_future(future)
            return await coro

    return inner
