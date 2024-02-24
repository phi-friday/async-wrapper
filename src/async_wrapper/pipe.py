from __future__ import annotations

from collections import deque
from contextlib import AsyncExitStack, suppress
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    Generic,
    Protocol,
    runtime_checkable,
)

import anyio
from typing_extensions import TypedDict, TypeVar, override

from async_wrapper.exception import PipeAlreadyDisposedError

if TYPE_CHECKING:
    from anyio.abc import CapacityLimiter, Lock, Semaphore

    class Synchronization(TypedDict, total=False):
        semaphore: Semaphore
        lock: Lock
        limiter: CapacityLimiter


__all__ = ["Disposable", "Pipe"]

InputT = TypeVar("InputT", infer_variance=True)
OutputT = TypeVar("OutputT", infer_variance=True)


@runtime_checkable
class Disposable(Protocol[InputT, OutputT]):
    async def next(self, value: InputT) -> OutputT: ...
    async def dispose(self) -> Any: ...


class Pipe(Disposable[InputT, OutputT], Generic[InputT, OutputT]):
    _context: Synchronization
    _listener: Callable[[InputT], Awaitable[OutputT]]
    _listeners: deque[tuple[Disposable[OutputT, Any], bool]]
    _dispose: Callable[[], Awaitable[Any]] | None
    _is_disposed: bool
    _dispose_lock: Lock

    __slots__ = (
        "_context",
        "_listener",
        "_listeners",
        "_dispose",
        "_is_disposed",
        "_dispose_lock",
    )

    def __init__(
        self,
        listener: Callable[[InputT], Awaitable[OutputT]],
        context: Synchronization | None = None,
        dispose: Callable[[], Awaitable[Any]] | None = None,
    ) -> None:
        self._listener = listener
        self._context = context or {}
        self._listeners = deque()
        self._dispose = dispose
        self._is_disposed = False
        self._dispose_lock = anyio.Lock()

    @override
    async def next(self, value: InputT) -> OutputT:
        if self._is_disposed:
            raise PipeAlreadyDisposedError("pipe already disposed")

        output = await self._listener(value)

        async with anyio.create_task_group() as task_group:
            for listener, _ in self._listeners:
                task_group.start_soon(_call_next, self._context, listener, output)

        return output

    @override
    async def dispose(self) -> None:
        async with self._dispose_lock:
            if self._is_disposed:
                return

            async with anyio.create_task_group() as task_group:
                if self._dispose is not None:
                    task_group.start_soon(_call_dispose, self._context, self._dispose)

                for listener, do_dispose in self._listeners:
                    if not do_dispose:
                        continue
                    task_group.start_soon(_call_dispose, self._context, listener)

            self._is_disposed = True

    def subscribe(
        self,
        listener: Disposable[OutputT, Any] | Callable[[OutputT], Awaitable[Any]],
        *,
        dispose: bool = True,
    ) -> None:
        if self._is_disposed:
            raise PipeAlreadyDisposedError("pipe already disposed")

        if not isinstance(listener, Disposable):
            listener = Pipe(listener)
        self._listeners.append((listener, dispose))


async def _enter_context(stack: AsyncExitStack, context: Synchronization) -> None:
    semaphore = context.get("semaphore")
    if semaphore is not None:
        await stack.enter_async_context(semaphore)

    limiter = context.get("limiter")
    if limiter is not None:
        await stack.enter_async_context(limiter)

    lock = context.get("lock")
    if lock is not None:
        await stack.enter_async_context(lock)


async def _call_next(
    context: Synchronization, disposable: Disposable[InputT, Any], value: InputT
) -> None:
    async with AsyncExitStack() as stack:
        await _enter_context(stack, context)
        with suppress(PipeAlreadyDisposedError):
            await disposable.next(value)


async def _call_dispose(
    context: Synchronization,
    disposable: Disposable[Any, Any] | Callable[[], Awaitable[Any]],
) -> None:
    async with AsyncExitStack() as stack:
        await _enter_context(stack, context)

        if isinstance(disposable, Disposable):
            await disposable.dispose()
        else:
            await disposable()
