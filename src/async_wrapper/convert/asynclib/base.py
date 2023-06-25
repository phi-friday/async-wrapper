from __future__ import annotations

from typing import Any, Callable, Coroutine, Protocol, TypeVar

from typing_extensions import ParamSpec

ValueT = TypeVar("ValueT")
ParamT = ParamSpec("ParamT")

__all__ = ["SyncToAsync"]


class SyncToAsync(Protocol):
    def __call__(  # noqa: D102
        self,
        func: Callable[ParamT, ValueT],
    ) -> Callable[ParamT, Coroutine[Any, Any, ValueT]]:
        ...
