from __future__ import annotations

from abc import ABC, abstractmethod
from threading import local
from typing import Any, Awaitable, Callable, Generic, TypeVar

from typing_extensions import ParamSpec

from async_wrapper.convert.synclib.base import as_coro_func

TaskGroupT = TypeVar("TaskGroupT")
ValueT = TypeVar("ValueT")
ValueT_co = TypeVar("ValueT_co", covariant=True)
ParamT = ParamSpec("ParamT")
Pending = local()

__all__ = ["PendingError", "BaseSoonWrapper", "SoonValue"]


class PendingError(Exception):
    ...


class BaseSoonWrapper(ABC, Generic[TaskGroupT, ParamT, ValueT]):
    def __init__(
        self,
        func: Callable[ParamT, Awaitable[ValueT]],
        task_group: TaskGroupT,
    ) -> None:
        self.func = as_coro_func(func)
        self.task_group = task_group

    @abstractmethod
    def __call__(  # noqa: D102
        self,
        *args: ParamT.args,
        **kwargs: ParamT.kwargs,
    ) -> SoonValue[ValueT]:
        ...


class SoonValue(Generic[ValueT_co]):
    def __init__(self) -> None:
        self._value = Pending

    @property
    def value(self) -> ValueT_co:  # noqa: D102
        if self._value is Pending:
            raise PendingError
        return self._value  # type: ignore

    @value.setter
    def value(self, value: Any) -> None:
        self._value = value

    @value.deleter
    def value(self) -> None:
        raise NotImplementedError
