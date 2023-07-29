from __future__ import annotations

import inspect
import math
from abc import ABC, abstractmethod
from collections import deque
from contextlib import AbstractAsyncContextManager
from functools import partial, wraps
from threading import local
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    Coroutine,
    Generator,
    Generic,
    Iterable,
    Literal,
    Protocol,
    TypeVar,
    final,
)

import anyio
from typing_extensions import ParamSpec, Self, override

if TYPE_CHECKING:
    from contextvars import Context
    from types import TracebackType
    from weakref import WeakSet

    from anyio.abc import Event as AnyioEvent
    from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream

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


class StreamQueue(Generic[ValueT]):
    def __init__(self, size: float = 0) -> None:
        setter, getter = anyio.create_memory_object_stream(size)
        self.getter: MemoryObjectReceiveStream[ValueT] = getter
        self.setter: MemoryObjectSendStream[ValueT] = setter

    def set(self, value: ValueT) -> None:  # noqa: A003
        self.setter.send_nowait(value)

    async def aset(self, value: ValueT) -> None:
        await self.setter.send(value)

    def get(self) -> ValueT:
        return self.getter.receive_nowait()

    async def aget(self) -> ValueT:
        return await self.getter.receive()

    def touch(self) -> ValueT:
        result = self.getter.receive_nowait()
        self.setter.send_nowait(result)
        return result

    async def atouch(self) -> ValueT:
        result = await self.getter.receive()
        await self.setter.send(result)
        return result

    @property
    def size(self) -> int:
        status = self.getter.statistics()
        return status.current_buffer_used


@final
class Future(Generic[ValueT_co, TaskGroupT_co]):
    def __init__(
        self,
        coro: Coroutine[Any, Any, ValueT_co],
        task_group: TaskGroupT_co,
    ) -> None:
        if inspect.getcoroutinestate(coro) != "CORO_CREATED":
            raise RuntimeError("future use only created coro")

        self.coro = coro
        self.task_group = task_group

        self.exc: BaseException | None = None
        self.value_queue: StreamQueue[ValueT_co] = StreamQueue(1)

        self.callbacks: deque[tuple[Callable[[Self], Any], Context | None]] = deque()
        self.final_callbacks: StreamQueue[Callable[[Self], Any]] = StreamQueue(1)

    def dummy(self, event: AnyioEvent) -> Future[Any, TaskGroupT_co]:
        return Future(_dummy(event), self.task_group)

    @property
    def running(self) -> bool:
        return self.coro_state != "CORO_CREATED"

    @property
    def done(self) -> bool:
        return self.coro_state == "CORO_CLOSED"

    @property
    def pending(self) -> bool:
        return self.coro_state not in {"CORO_CREATED", "CORO_CLOSED"}

    @property
    def cancelled(self) -> bool:
        return self.exc is not None

    @property
    def coro_state(
        self,
    ) -> Literal["CORO_CREATED", "CORO_RUNNING", "CORO_SUSPENDED", "CORO_CLOSED"]:
        return inspect.getcoroutinestate(self.coro)

    def __repr__(self) -> str:
        if self.cancelled:
            state = "error"
        else:
            state = self.coro_state
            if state == "CORO_CREATED":
                state = "before running"
            elif state == "CORO_CLOSED":
                state = "finished"
            else:
                state = "pending"

        return f"<future: state={state}>"

    def __await__(self) -> Generator[Any, None, ValueT_co]:
        if self.running:
            raise RuntimeError("coro has already running")

        try:
            result = yield from self.coro.__await__()
        except BaseException as exc:
            self.exc = exc

            while self.final_callbacks.size:
                callback = self.final_callbacks.get()
                callback(self)

            raise

        self.value_queue.set(result)

        try:
            return result
        finally:
            if self.callbacks:
                for callback, context in self.callbacks:
                    if context is None:
                        callback(self)
                    else:
                        context.run(callback, self)
                self.callbacks.clear()

            while self.final_callbacks.size:
                callback = self.final_callbacks.get()
                callback(self)

    def exception(self) -> BaseException | None:
        if not self.running:
            raise RuntimeError("await first")
        return self.exc

    def result(self) -> ValueT_co:
        if not self.running:
            raise RuntimeError("await first")
        if not self.done:
            raise RuntimeError("still await")
        if self.cancelled:
            raise self.exc  # type: ignore
        return self.value_queue.touch()

    def add_done_callback(
        self,
        __fn: Callable[[Self], Any],
        *,
        context: Context | None = None,
    ) -> None:
        self.callbacks.append((__fn, context))

    def add_final_callback(self, func: Callable[[Self], Any]) -> None:
        self.final_callbacks.set(func)


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
    def tasks(self) -> WeakSet[Future[Any, Self]]:
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

    async def wait(self, tasks: Iterable[Future[Any, Self]]) -> None:
        await _wait(tasks)

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
        future: Future[ValueT_co, Any] | None = None,
    ) -> None:
        self._value = Pending
        if future is None:
            self._future = None
        else:
            self._set_future(future)

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

    def _set_future(
        self,
        future: Future[ValueT_co, Any],
    ) -> None:
        if self._value is not Pending:
            raise AttributeError("value is already setted")
        future.add_done_callback(self._set_from_future)
        self._future = future

    def _set_from_future(
        self,
        future: Future[ValueT_co, Any],
    ) -> None:
        if future.exception() is None:
            self.value = future.result()
        if self._future is not None:
            self._future = None


class TaskGroupFactory(Protocol[TaskGroupT_co]):
    def __call__(self) -> TaskGroupT_co:  # noqa: D102
        ...


async def _wait(
    futures: Iterable[Future[Any, Any]],
    timeout: float | None = None,
) -> None:
    futures = set(futures)
    if not futures:
        return

    async with anyio.create_task_group() as task_group:
        for future in futures:
            task_group.start_soon(_await, future, timeout)


async def _await(future: Future[Any, Any], timeout: float | None) -> None:
    if future.done:
        return

    event = anyio.Event()
    waiter = future.dummy(event)
    scope = anyio.CancelScope(shield=True, deadline=timeout or math.inf)
    callback = partial(_release, event=event, scope=scope)
    future.add_final_callback(callback)

    async with anyio.maybe_async_cm(anyio.fail_after(timeout)):
        await waiter


def _release(
    future: Future[Any, Any],
    event: AnyioEvent,
    scope: anyio.CancelScope,
) -> None:
    if not future.running:
        raise RuntimeError("call future first")
    with scope:
        event.set()


async def _dummy(event: AnyioEvent) -> None:
    await event.wait()
