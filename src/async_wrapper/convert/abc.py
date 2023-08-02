from __future__ import annotations

from typing import Any, Awaitable, Callable, Coroutine, Protocol, TypeVar, overload

from typing_extensions import ParamSpec

ValueT_co = TypeVar("ValueT_co", covariant=True)
ParamT = ParamSpec("ParamT")

__all__ = ["SyncToAsync", "AsyncToSync", "Toggle"]


class SyncToAsync(Protocol):
    def __call__(  # noqa: D102
        self,
        func: Callable[ParamT, ValueT_co],
    ) -> Callable[ParamT, Coroutine[Any, Any, ValueT_co]]:
        ...


class AsyncToSync(Protocol):
    def __call__(  # noqa: D102
        self,
        func: Callable[ParamT, Awaitable[ValueT_co]],
    ) -> Callable[ParamT, ValueT_co]:
        ...


class Toggle(Protocol):
    @overload
    def __call__(
        self,
        func: Callable[ParamT, Coroutine[Any, Any, ValueT_co]],
    ) -> Callable[ParamT, ValueT_co]:
        ...

    @overload
    def __call__(
        self,
        func: Callable[ParamT, ValueT_co],
    ) -> Callable[ParamT, Coroutine[Any, Any, ValueT_co]]:
        ...

    def __call__(  # noqa: D102
        self,
        func: Callable[ParamT, ValueT_co]
        | Callable[ParamT, Coroutine[Any, Any, ValueT_co]],
    ) -> Callable[ParamT, ValueT_co] | Callable[ParamT, Coroutine[Any, Any, ValueT_co]]:
        ...
