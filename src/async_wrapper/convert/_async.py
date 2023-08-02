from __future__ import annotations

from functools import partial, wraps
from typing import Any, Callable, Coroutine, TypeVar

import anyio
from typing_extensions import ParamSpec

ValueT = TypeVar("ValueT")
ParamT = ParamSpec("ParamT")

__all__ = ["sync_to_async"]


def sync_to_async(
    func: Callable[ParamT, ValueT],
) -> Callable[ParamT, Coroutine[Any, Any, ValueT]]:
    @wraps(func)
    async def inner(*args: ParamT.args, **kwargs: ParamT.kwargs) -> ValueT:
        return await anyio.to_thread.run_sync(partial(func, *args, **kwargs))

    return inner
