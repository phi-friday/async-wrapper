from __future__ import annotations

import inspect
import math
from collections import deque
from contextlib import contextmanager
from functools import partial
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Coroutine,
    Generator,
    Generic,
    Literal,
    TypeVar,
)

import anyio

if TYPE_CHECKING:
    from contextvars import Context
    from types import TracebackType

    from anyio.abc import CancelScope
    from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
    from typing_extensions import Self

__all__ = ["Future", "Waiter"]

ValueT = TypeVar("ValueT")
ValueT_co = TypeVar("ValueT_co", covariant=True)


class StreamQueue(Generic[ValueT]):
    def __init__(self, size: float = 0) -> None:
        setter, getter = anyio.create_memory_object_stream(size)
        self.getter: MemoryObjectReceiveStream[ValueT] = getter
        self.setter: MemoryObjectSendStream[ValueT] = setter

    def set(self, value: ValueT) -> None:  # noqa: A003
        """set value in queue

        Args:
            value: value
        """
        self.setter.send_nowait(value)

    async def aset(self, value: ValueT) -> None:
        """async set value in queue

        Args:
            value: value
        """
        await self.setter.send(value)

    def get(self) -> ValueT:
        """get value in queue

        Returns:
            value if exists
        """
        return self.getter.receive_nowait()

    async def aget(self) -> ValueT:
        """async get value in queue

        Returns:
            value if exists
        """
        return await self.getter.receive()

    def touch(self) -> ValueT:
        """get value and set immediately

        Returns:
            value if exists
        """
        result = self.get()
        self.set(result)
        return result

    async def atouch(self) -> ValueT:
        """async get value and async set immediately

        Returns:
            value if exists
        """
        result = await self.aget()
        await self.aset(result)
        return result

    @property
    def size(self) -> int:
        """used queue buffer size

        Returns:
            size(>=0)
        """
        status = self.getter.statistics()
        return status.current_buffer_used

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.getter.close()
        self.setter.close()


class Future(Generic[ValueT_co]):
    def __init__(self, coro: Coroutine[Any, Any, ValueT_co]) -> None:
        if inspect.getcoroutinestate(coro) != "CORO_CREATED":
            raise RuntimeError("future use only created coro")

        self.coro = coro

        self.exc: BaseException | None = None
        self.value: StreamQueue[ValueT_co] = StreamQueue(1)
        self._is_ended = False

        self.callbacks: deque[tuple[Callable[[Self], Any], Context | None]] = deque()
        self.final_callbacks: StreamQueue[Callable[[Self], Any]] = StreamQueue(math.inf)

    @property
    def is_begin(self) -> bool:
        """check future is already start

        Returns:
            True if started
        """
        return self._coro_state != "CORO_CREATED"

    @property
    def done(self) -> bool:
        """check future is ended.

        without callback.

        Returns:
            True if future done
        """
        return self._coro_state == "CORO_CLOSED"

    @property
    def is_ended(self) -> bool:
        """check future is ended.

        Returns:
            True if future ended
        """
        return self._is_ended

    @property
    def pending(self) -> bool:
        """check future is running

        Returns:
            True if future is running
        """
        return self._coro_state not in {"CORO_CREATED", "CORO_CLOSED"}

    @property
    def cancelled(self) -> bool:
        """check future is end but cancelled

        Returns:
            True if future has error
        """
        return self.exc is not None

    @property
    def _coro_state(
        self,
    ) -> Literal["CORO_CREATED", "CORO_RUNNING", "CORO_SUSPENDED", "CORO_CLOSED"]:
        return inspect.getcoroutinestate(self.coro)

    def __repr__(self) -> str:
        if self.cancelled:
            state = "error"
        else:
            state = self._coro_state
            if state == "CORO_CREATED":
                state = "before running"
            elif state == "CORO_CLOSED":
                state = "finished"
            else:
                state = "pending"

        return f"<future: state={state}>"

    def __await__(self) -> Generator[Any, None, ValueT_co]:
        if self.is_begin:
            raise RuntimeError("future has already running")

        try:
            result = yield from self.coro.__await__()
        except Exception as exc:  # noqa: BLE001
            self.exc = exc
            with self._run_final_callbacks():
                raise

        yield from self.value.aset(result).__await__()

        with self._run_final_callbacks():
            with self._run_done_callbacks():
                return result

    def exception(self) -> BaseException | None:
        """get error after running

        Returns:
            error or null
        """
        if not self.is_begin:
            raise RuntimeError("await first")
        return self.exc

    def result(self) -> ValueT_co:
        """get future result after running

        Returns:
            future result
        """
        if not self.is_begin:
            raise RuntimeError("await first")
        if not self.done:
            raise RuntimeError("still await")
        if self.cancelled:
            raise self.exc  # type: ignore
        return self.value.touch()

    def add_done_callback(
        self,
        func: Callable[[Self], Any],
        *,
        context: Context | None = None,
    ) -> None:
        """add done callback

        Args:
            func: future callback
            context: from contextvar. Defaults to None.
        """
        self.callbacks.append((func, context))

    def add_final_callback(self, func: Callable[[Self], Any]) -> None:
        """add final callback.

        Args:
            func: final callback
        """
        self.final_callbacks.set(func)

    async def wait(self, timeout: float | None = None) -> None:
        """wait self ended

        Args:
            timeout: timeout. Defaults to None.
        """
        waiter = Waiter()
        await waiter.wait(self, timeout=timeout)

    async def __call__(self) -> ValueT_co:
        """future to coro

        Returns:
            coro
        """
        return await self

    @contextmanager
    def _run_done_callbacks(self) -> Generator[None, None, None]:
        try:
            yield
        finally:
            while self.callbacks:
                callback, context = self.callbacks.popleft()
                if context is None:
                    callback(self)
                else:
                    context.run(callback, self)

    @contextmanager
    def _run_final_callbacks(self) -> Generator[None, None, None]:
        try:
            yield
        finally:
            self._is_ended = True
            while self.final_callbacks.size:
                callback = self.final_callbacks.get()
                callback(self)


class Waiter:
    def __init__(self) -> None:
        self.event = anyio.Event()

    async def wait(self, future: Future[Any], timeout: float | None = None) -> None:
        """wait future

        Args:
            future: target future
            timeout: timeout. Defaults to None.
        """
        if future.done:
            return

        scope = anyio.CancelScope(shield=True, deadline=timeout or math.inf)
        callback = partial(self._release, scope=scope)
        future.add_final_callback(callback)
        waiter = Future(self())

        with anyio.move_on_after(timeout, shield=True):
            await waiter

    def _release(self, future: Future[Any], scope: CancelScope) -> None:
        if not future.is_begin:
            raise RuntimeError("future is not begin")

        with scope:
            self.event.set()

    async def __call__(self) -> None:  # noqa: D102
        await self.event.wait()
