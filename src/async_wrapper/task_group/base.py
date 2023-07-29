from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import AbstractAsyncContextManager, suppress
from functools import wraps
from threading import local
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    Coroutine,
    Generator,
    Generic,
    Protocol,
    TypeVar,
)

import anyio
from typing_extensions import ParamSpec, Self, override

if TYPE_CHECKING:
    from contextvars import Context
    from types import TracebackType
    from weakref import WeakSet

TaskGroupT = TypeVar("TaskGroupT", bound="BaseTaskGroup")
TaskGroupT_co = TypeVar("TaskGroupT_co", covariant=True, bound="BaseTaskGroup")
ValueT = TypeVar("ValueT")
ValueT_co = TypeVar("ValueT_co", covariant=True)
OtherValueT_co = TypeVar("OtherValueT_co", covariant=True)
ParamT = ParamSpec("ParamT")
OtherParamT = ParamSpec("OtherParamT")
Pending = local()

__all__ = ["PendingError", "BaseSoonWrapper", "SoonValue", "TaskGroupFactory"]


class PendingError(Exception):
    ...


class Semaphore(AbstractAsyncContextManager, Protocol):
    async def acquire(self) -> Any:
        ...


class Futurelike(Protocol, Generic[ValueT_co]):
    def __await__(self) -> Generator[Any, None, ValueT_co]:
        ...

    def exception(self) -> BaseException | None:
        ...

    def result(self) -> ValueT_co:
        ...

    def add_done_callback(
        self,
        __fn: Callable[[Self], Any],
        *,
        context: Context | None = None,
    ) -> None:
        ...


class BaseTaskGroup(ABC):
    @abstractmethod
    def start_soon(
        self,
        func: Callable[ParamT, Coroutine[Any, Any, ValueT_co]],
        *args: ParamT.args,
        **kwargs: ParamT.kwargs,
    ) -> SoonValue[ValueT_co]:
        ...

    @property
    @abstractmethod
    def is_active(self) -> bool:
        ...

    @property
    @abstractmethod
    def tasks(self) -> WeakSet[Futurelike[Any]]:
        ...

    @abstractmethod
    async def __aenter__(self) -> Self:
        ...

    @abstractmethod
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> Any:
        ...

    @staticmethod
    def _wrap(
        func: Callable[ParamT, Awaitable[ValueT_co]],
        semaphore: Semaphore | None = None,
    ) -> Callable[ParamT, Coroutine[Any, Any, ValueT_co]]:
        @wraps(func)
        async def wrapped(*args: ParamT.args, **kwargs: ParamT.kwargs) -> ValueT_co:
            if semaphore is None:
                return await func(*args, **kwargs)
            async with semaphore:
                return await func(*args, **kwargs)

        return wrapped


class BaseSoonWrapper(ABC, Generic[TaskGroupT, ParamT, ValueT_co]):
    def __init__(
        self,
        func: Callable[ParamT, Awaitable[ValueT_co]],
        task_group: TaskGroupT,
        semaphore: Semaphore | None = None,
    ) -> None:
        self.func = func
        self.task_group = task_group
        self.semaphore = semaphore

    @override
    def __new__(
        cls,
        func: Callable[OtherParamT, Awaitable[OtherValueT_co]],
        task_group: TaskGroupT,
        semaphore: Semaphore | None = None,
    ) -> BaseSoonWrapper[TaskGroupT, OtherParamT, OtherValueT_co]:
        return super().__new__(cls)  # type: ignore

    @abstractmethod
    def __call__(  # noqa: D102
        self,
        *args: ParamT.args,
        **kwargs: ParamT.kwargs,
    ) -> SoonValue[ValueT_co]:
        ...

    @abstractmethod
    def copy(self, semaphore: Semaphore | None = None) -> Self:  # noqa: D102
        ...


class SoonValue(Generic[ValueT_co]):
    def __init__(
        self,
        task_or_future: Futurelike[ValueT_co] | None = None,
    ) -> None:
        self._value = Pending
        if task_or_future is None:
            self._task_or_future = None
        else:
            self._set_task_or_future(task_or_future)

    def __repr__(self) -> str:
        status = "pending" if self._value is Pending else "done"
        return f"<SoonValue: status={status}>"

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

    @property
    def is_ready(self) -> bool:  # noqa: D102
        return self._value is not Pending

    def result(  # noqa: D102
        self,
        *,
        timeout: float | None = None,
    ) -> ValueT_co:
        with suppress(PendingError):
            return self.value

        task = self._task_or_future
        if task is None:
            with suppress(PendingError):
                return self.value
            raise AttributeError("task is None")

        async def wrap_task() -> ValueT_co:
            task = self._task_or_future
            if task is None:
                with suppress(PendingError):
                    return self.value
                raise AttributeError("task is None")
            return await _wait_for(task, timeout)

        return anyio.from_thread.run(wrap_task)

    def _set_task_or_future(
        self,
        task_or_future: Futurelike[ValueT_co],
    ) -> None:
        if self._value is not Pending:
            raise AttributeError("value is already setted")
        task_or_future.add_done_callback(self._set_from_task_or_future)
        self._task_or_future = task_or_future

    def _set_from_task_or_future(
        self,
        task_or_future: Futurelike[ValueT_co],
    ) -> None:
        if task_or_future.exception() is None:
            self.value = task_or_future.result()
        if self._task_or_future is not None:
            self._task_or_future = None


class TaskGroupFactory(Protocol[TaskGroupT_co]):
    def __call__(self) -> TaskGroupT_co:  # noqa: D102
        ...


async def _wait_for(
    future: Futurelike[ValueT_co],
    timeout: float | None = None,
) -> ValueT_co:
    async with anyio.maybe_async_cm(anyio.fail_after(timeout)):
        return await future
