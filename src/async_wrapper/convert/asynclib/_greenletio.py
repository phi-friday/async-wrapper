from __future__ import annotations

from typing import Any, Callable, Coroutine, TypeVar

from greenletio import async_
from typing_extensions import ParamSpec

ValueT = TypeVar("ValueT")
ParamT = ParamSpec("ParamT")

__all__ = ["sync_to_async"]


def sync_to_async(
    func: Callable[ParamT, ValueT],
) -> Callable[ParamT, Coroutine[Any, Any, ValueT]]:
    return async_(func)  # type: ignore
