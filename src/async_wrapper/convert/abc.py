from __future__ import annotations

from typing import Any, Awaitable, Callable, Coroutine, Protocol, TypeVar, overload

from typing_extensions import ParamSpec

ValueT_co = TypeVar("ValueT_co", covariant=True)
ParamT = ParamSpec("ParamT")

__all__ = ["SyncToAsync", "AsyncToSync", "Toggle"]


class SyncToAsync(Protocol):
    """convert sync func to async"""

    def __call__(  # noqa: D102
        self,
        func: Callable[ParamT, ValueT_co],
    ) -> Callable[ParamT, Coroutine[Any, Any, ValueT_co]]:
        ...  # pragma: no cover


class AsyncToSync(Protocol):
    """convert awaitable func to sync"""

    def __call__(  # noqa: D102
        self,
        func: Callable[ParamT, Awaitable[ValueT_co]],
    ) -> Callable[ParamT, ValueT_co]:
        ...  # pragma: no cover


class Toggle(Protocol):
    """convert sync func to async. or awaitable func to sync."""

    @overload
    def __call__(
        self,
        func: Callable[ParamT, Coroutine[Any, Any, ValueT_co]],
    ) -> Callable[ParamT, ValueT_co]:
        ...  # pragma: no cover

    @overload
    def __call__(
        self,
        func: Callable[ParamT, ValueT_co],
    ) -> Callable[ParamT, Coroutine[Any, Any, ValueT_co]]:
        ...  # pragma: no cover

    def __call__(  # noqa: D102
        self,
        func: Callable[ParamT, ValueT_co]
        | Callable[ParamT, Coroutine[Any, Any, ValueT_co]],
    ) -> Callable[ParamT, ValueT_co] | Callable[ParamT, Coroutine[Any, Any, ValueT_co]]:
        ...  # pragma: no cover
