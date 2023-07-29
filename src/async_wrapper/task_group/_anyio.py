from __future__ import annotations

import math
from collections import deque
from functools import partial
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    Coroutine,
    Generator,
    Generic,
    Iterable,
    TypeVar,
    final,
)
from weakref import WeakSet

from anyio import (
    CancelScope,
    create_memory_object_stream,
    create_task_group,
    fail_after,
    maybe_async_cm,
)
from anyio import Event as _Event
from anyio import Semaphore as _Semaphore
from typing_extensions import ParamSpec, Self, override

from async_wrapper.task_group.base import (
    BaseSoonWrapper,
    BaseTaskGroup,
    Semaphore,
    SoonValue,
)

if TYPE_CHECKING:
    from contextvars import Context
    from types import TracebackType

    from anyio.abc import Event as AnyioEvent
    from anyio.abc import Semaphore as AnyioSemaphore  # type: ignore
    from anyio.abc import TaskGroup as _TaskGroup
    from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream

    from async_wrapper.task_group.base import Futurelike


ValueT = TypeVar("ValueT")
ValueT_co = TypeVar("ValueT_co", covariant=True)
OtherValueT_co = TypeVar("OtherValueT_co", covariant=True)
ParamT = ParamSpec("ParamT")
OtherParamT = ParamSpec("OtherParamT")

__all__ = ["SoonWrapper", "wrap_soon", "get_task_group", "get_semaphore_class"]


class CancelError(Exception):
    ...


class StreamQueue(Generic[ValueT]):
    def __init__(self, size: float = 0) -> None:
        setter, getter = create_memory_object_stream(size)
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


class Future(Generic[ValueT_co]):
    def __init__(self, coro: Coroutine[Any, Any, ValueT_co]) -> None:
        self.coro = coro
        self.exc: BaseException | None = None

        self.value_queue: StreamQueue[ValueT_co] = StreamQueue(1)

        self.running: bool = False
        self.done: bool = False
        self.canceled: bool = False

        self.callbacks: deque[tuple[Callable[[Self], Any], Context | None]] = deque()
        self.final_callbacks: StreamQueue[Callable[[Self], Any]] = StreamQueue(1)

    @classmethod
    def new(cls, event: AnyioEvent) -> Self:
        return cls(_dummy(event))

    def __repr__(self) -> str:
        return (
            "<future: "
            f"running={self.running}, done={self.done}, cancel={self.canceled}>"
        )

    def __await__(self) -> Generator[Any, None, ValueT_co]:
        self.running = True
        try:
            result = yield from self.coro.__await__()
        except BaseException as exc:
            self.exc = exc
            self.done = True
            self.canceled = True

            while self.final_callbacks.size:
                callback = self.final_callbacks.get()
                callback(self)

            raise

        self.done = True
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
        if self.canceled:
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


class TaskGroup(BaseTaskGroup):
    def __init__(self) -> None:
        self._task_group: _TaskGroup = create_task_group()
        self._futures: WeakSet[Future[Any]] = WeakSet()

    @override
    def start_soon(
        self,
        func: Callable[ParamT, Coroutine[Any, Any, ValueT_co]],
        *args: ParamT.args,
        **kwargs: ParamT.kwargs,
    ) -> SoonValue[ValueT_co]:
        value = SoonValue()
        future = self._as_future(func, *args, **kwargs)
        value._set_task_or_future(future)  # noqa: SLF001
        self._task_group.start_soon(_as_coro, future)
        return value

    def _as_future(
        self,
        func: Callable[ParamT, Coroutine[Any, Any, ValueT_co]],
        *args: ParamT.args,
        **kwargs: ParamT.kwargs,
    ) -> Futurelike[ValueT_co]:
        coro = func(*args, **kwargs)
        future = Future(coro)
        self._futures.add(future)
        return future

    @property
    @override
    def is_active(self) -> bool:
        return self._task_group._active  # type: ignore # noqa: SLF001

    @property
    @override
    def tasks(self) -> WeakSet[Future[Any]]:
        return self._futures

    @override
    async def __aenter__(self) -> Self:
        await self._task_group.__aenter__()
        return self

    @override
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> Any:
        tasks = tuple(self.tasks)
        if tasks:
            await _wait(tasks)
        return await self._task_group.__aexit__(exc_type, exc, traceback)


@final
class SoonWrapper(
    BaseSoonWrapper[TaskGroup, ParamT, ValueT_co],
    Generic[ParamT, ValueT_co],
):
    if TYPE_CHECKING:

        @override
        def __new__(
            cls,
            func: Callable[OtherParamT, Awaitable[OtherValueT_co]],
            task_group: TaskGroup,
            semaphore: Semaphore | None = None,
        ) -> SoonWrapper[OtherParamT, OtherValueT_co]:
            ...

    @override
    def __call__(
        self,
        *args: ParamT.args,
        **kwargs: ParamT.kwargs,
    ) -> SoonValue[ValueT_co]:
        wrapped = self.task_group._wrap(self.func, self.semaphore)  # noqa: SLF001
        return self.task_group.start_soon(wrapped, *args, **kwargs)

    @override
    def copy(self, semaphore: Semaphore | None = None) -> Self:
        if semaphore is None:
            semaphore = self.semaphore
        return SoonWrapper(self.func, self.task_group, semaphore)


def get_semaphore_class() -> type[AnyioSemaphore]:
    return _Semaphore


async def _wait(
    futures: Iterable[Future[Any]],
    timeout: float | None = None,
) -> None:
    futures = set(futures)
    if not futures:
        return

    async with create_task_group() as task_group:
        for future in futures:
            task_group.start_soon(_await, future, timeout)


async def _await(future: Future[Any], timeout: float | None) -> None:
    if future.done:
        return

    event = _Event()
    waiter = Future.new(event)
    scope = CancelScope(shield=True, deadline=timeout or math.inf)
    callback = partial(_release, waiter=waiter, event=event, scope=scope)
    future.add_final_callback(callback)

    async with maybe_async_cm(fail_after(timeout)):
        await waiter


async def _as_coro(future: Futurelike[ValueT_co]) -> ValueT_co:
    return await future


def _release(
    future: Future[Any],  # noqa: ARG001
    waiter: Future[Any],
    event: AnyioEvent,
    scope: CancelScope,
) -> None:
    with scope:
        if not waiter.done:
            event.set()


async def _dummy(event: AnyioEvent) -> None:
    await event.wait()


wrap_soon = SoonWrapper
get_task_group = TaskGroup
