from __future__ import annotations

import threading
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

from async_wrapper.exception import AlreadyDisposedError

if TYPE_CHECKING:
    from anyio.abc import CapacityLimiter, Lock, Semaphore

    class Synchronization(TypedDict, total=False):
        semaphore: Semaphore
        lock: Lock
        limiter: CapacityLimiter


__all__ = [
    "Disposable",
    "DisposableWithCallback",
    "Subscribable",
    "SimpleDisposable",
    "Pipe",
    "create_disposable",
]

InputT = TypeVar("InputT", infer_variance=True)
OutputT = TypeVar("OutputT", infer_variance=True)


@runtime_checkable
class Disposable(Protocol[InputT, OutputT]):
    """Defines the interface for a disposable resource."""

    @property
    def is_disposed(self) -> bool:
        """Check if disposed"""
        ...  # pragma: no cover

    async def next(self, value: InputT) -> OutputT:
        """
        Processes the next input value and produces an output value.

        Args:
            value: The input value.

        Returns:
            The output value.
        """
        ...  # pragma: no cover

    async def dispose(self) -> Any:
        """Disposes the resource and releases any associated resources."""

    @override
    def __hash__(self) -> int: ...


@runtime_checkable
class DisposableWithCallback(Disposable[InputT, OutputT], Protocol[InputT, OutputT]):
    """disposable & callback"""

    def prepare_callback(self, subscribable: Subscribable[InputT, OutputT]) -> Any:
        """Prepare a callback to use when dispose is executed.

        Args:
            subscribable: subscribable object
        """


@runtime_checkable
class Subscribable(Disposable[InputT, OutputT], Protocol[InputT, OutputT]):
    """subscribable & disposable"""

    @property
    def size(self) -> int:
        """listener size"""
        ...  # pragma: no cover

    def subscribe(
        self,
        disposable: Disposable[OutputT, Any] | Callable[[OutputT], Awaitable[Any]],
        *,
        dispose: bool = True,
    ) -> Any:
        """
        Subscribes a disposable

        Args:
            disposable: The disposable to subscribe.
            dispose: Whether to dispose the disposable when the pipe is disposed.
        """

    def unsubscribe(self, disposable: Disposable[Any, Any]) -> None:
        """
        Unsubscribes a disposable

        Args:
            disposable: The disposable to unsubscribe.
        """


class SimpleDisposable(
    DisposableWithCallback[InputT, OutputT], Generic[InputT, OutputT]
):
    """simple disposable impl."""

    _journals: deque[Subscribable[InputT, OutputT]]
    __slots__ = ("_func", "_is_disposed", "_journals", "_async_lock", "_thread_lock")

    def __init__(self, func: Callable[[InputT], Awaitable[OutputT]]) -> None:
        self._func = func
        self._is_disposed = False
        self._journals = deque()
        self._async_lock = anyio.Lock()
        self._thread_lock = threading.Lock()

    @property
    @override
    def is_disposed(self) -> bool:
        return self._is_disposed

    @override
    async def next(self, value: InputT) -> OutputT:
        if self._is_disposed:
            raise AlreadyDisposedError("disposable already disposed")
        return await self._func(value)

    @override
    async def dispose(self) -> Any:
        async with self._async_lock:
            while self._journals:
                journal = self._journals.popleft()
                journal.unsubscribe(self)
        self._is_disposed = True

    @override
    def prepare_callback(self, subscribable: Subscribable[InputT, OutputT]) -> Any:
        if self._is_disposed:
            raise AlreadyDisposedError("disposable already disposed")

        with self._thread_lock:
            self._journals.append(subscribable)

    @override
    def __hash__(self) -> int:
        return hash((id(self), id(self._func)))


class Pipe(Subscribable[InputT, OutputT], Generic[InputT, OutputT]):
    """
    Implements a pipe that can be used to communicate data between coroutines.

    Args:
        listener: The function that will be called to process each input value.
        context: An optional synchronization context to use.
        dispose: An optional function that will be called to dispose the pipe.
    """

    _context: Synchronization
    _listener: Callable[[InputT], Awaitable[OutputT]]
    _listeners: dict[Disposable[OutputT, Any], bool]
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
        self._listeners = {}
        self._dispose = dispose
        self._is_disposed = False
        self._dispose_lock = anyio.Lock()

    @property
    @override
    def is_disposed(self) -> bool:
        return self._is_disposed

    @property
    @override
    def size(self) -> int:
        return len(self._listeners)

    @override
    async def next(self, value: InputT) -> OutputT:
        if self._is_disposed:
            raise AlreadyDisposedError("pipe already disposed")

        output = await self._listener(value)

        async with anyio.create_task_group() as task_group:
            for listener in self._listeners:
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

                for listener, do_dispose in self._listeners.items():
                    if not do_dispose:
                        continue
                    task_group.start_soon(_call_dispose, self._context, listener)

            self._is_disposed = True

    @override
    def subscribe(
        self,
        disposable: Disposable[OutputT, Any] | Callable[[OutputT], Awaitable[Any]],
        *,
        dispose: bool = True,
    ) -> None:
        if self._is_disposed:
            raise AlreadyDisposedError("pipe already disposed")

        if not isinstance(disposable, Disposable):
            disposable = SimpleDisposable(disposable)
        self._listeners[disposable] = dispose
        if isinstance(disposable, DisposableWithCallback):
            disposable.prepare_callback(self)

    @override
    def unsubscribe(self, disposable: Disposable[Any, Any]) -> None:
        self._listeners.pop(disposable, None)

    @override
    def __hash__(self) -> int:
        return hash((id(self), id(self._listener)))


def create_disposable(
    func: Callable[[InputT], Awaitable[OutputT]],
) -> SimpleDisposable[InputT, OutputT]:
    """SimpleDisposable shortcut

    Args:
        func: awaitable function.

    Returns:
        SimpleDisposable object
    """
    return SimpleDisposable(func)


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
        with suppress(AlreadyDisposedError):
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
