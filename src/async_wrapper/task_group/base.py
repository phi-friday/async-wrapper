from __future__ import annotations

from abc import ABC, abstractmethod
from asyncio import wait
from contextlib import AbstractAsyncContextManager, suppress
from threading import local
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    Generic,
    Protocol,
    TypeVar,
)

from typing_extensions import ParamSpec, Self, override

from async_wrapper import async_to_sync

if TYPE_CHECKING:
    from asyncio import Future, Task
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


class BaseTaskGroup(ABC):
    _semaphore: Semaphore | None

    @abstractmethod
    def start_soon(
        self,
        func: Callable[ParamT, Awaitable[ValueT_co]],
        *args: ParamT.args,
        **kwargs: ParamT.kwargs,
    ) -> SoonValue[ValueT_co]:
        ...

    @property
    @abstractmethod
    def is_active(self) -> bool:
        ...

    @property
    def semaphore(self) -> Semaphore:
        if self._semaphore is None:
            raise AttributeError("there is no Semaphore")
        return self._semaphore

    @semaphore.setter
    def semaphore(self, value: Semaphore) -> None:
        self._semaphore = value

    @semaphore.deleter
    def semaphore(self) -> None:
        self._semaphore = None

    @property
    @abstractmethod
    def tasks(self) -> WeakSet[Task[Any]]:
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

    async def __call__(self, coro: Awaitable[ValueT_co]) -> ValueT_co:
        if self._semaphore is None:
            return await coro

        async with self.semaphore:
            return await coro


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

        if semaphore is not None:
            self.task_group.semaphore = semaphore

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
        task_or_future: Task[ValueT_co] | Future[ValueT_co] | None = None,
    ) -> None:
        self._value = Pending
        if task_or_future is None:
            self._task_or_future = None
        else:
            self.set_task_or_future(task_or_future)

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

        async def wrap_task() -> ValueT_co:
            task = self._task_or_future
            if task is None:
                with suppress(PendingError):
                    return self.value
                raise AttributeError("task is None")
            _, pending = await wait([task], timeout=timeout)
            if pending:
                error_msg = f"timeout! > {timeout}s"
                raise TimeoutError(error_msg)
            return await task

        return async_to_sync("thread")(wrap_task)()

    def set_task_or_future(  # noqa: D102
        self,
        task_or_future: Task[ValueT_co] | Future[ValueT_co],
    ) -> None:
        if self._value is not Pending:
            raise AttributeError("value is already setted")
        task_or_future.add_done_callback(self.set_from_task_or_future)
        self._task_or_future = task_or_future

    def set_from_task_or_future(  # noqa: D102
        self,
        task_or_future: Task[ValueT_co] | Future[ValueT_co],
    ) -> None:
        if task_or_future.exception() is None:
            self.value = task_or_future.result()
        if self._task_or_future is not None:
            self._task_or_future = None

    async def catch_and_set(  # noqa: D102
        self,
        func: Callable[ParamT, Awaitable[ValueT_co]],
        *args: ParamT.args,
        **kwargs: ParamT.kwargs,
    ) -> Self:
        self.value = await func(*args, **kwargs)
        return self


class TaskGroupFactory(Protocol[TaskGroupT_co]):
    def __call__(self) -> TaskGroupT_co:  # noqa: D102
        ...
