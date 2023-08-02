from __future__ import annotations

from functools import partial, wraps
from typing import Any, Callable, Coroutine, TypeVar

import anyio
from typing_extensions import ParamSpec

ValueT_co = TypeVar("ValueT_co", covariant=True)
ParamT = ParamSpec("ParamT")

__all__ = ["sync_to_async"]


def sync_to_async(
    func: Callable[ParamT, ValueT_co],
) -> Callable[ParamT, Coroutine[Any, Any, ValueT_co]]:
    @wraps(func)
    async def inner(*args: ParamT.args, **kwargs: ParamT.kwargs) -> ValueT_co:
        return await anyio.to_thread.run_sync(partial(func, *args, **kwargs))

    return inner
