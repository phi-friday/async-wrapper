from __future__ import annotations

import math
import sys
from contextlib import asynccontextmanager, contextmanager
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncContextManager,
    AsyncGenerator,
    ContextManager,
    Generator,
    Generic,
    TypeVar,
)

from anyio import WouldBlock, create_memory_object_stream, create_task_group, fail_after
from anyio.streams.memory import BrokenResourceError, ClosedResourceError, EndOfStream

from async_wrapper.exception import (
    QueueBrokenError,
    QueueClosedError,
    QueueEmptyError,
    QueueFullError,
)

if sys.version_info < (3, 11):  # pragma: no cover
    from exceptiongroup import ExceptionGroup  # type: ignore

if TYPE_CHECKING:
    from types import TracebackType

    from anyio.streams.memory import (
        MemoryObjectReceiveStream,
        MemoryObjectSendStream,
        MemoryObjectStreamStatistics,
    )
    from typing_extensions import Self

__all__ = ["Queue", "create_queue"]

ValueT = TypeVar("ValueT")


class Queue(Generic[ValueT]):
    """obtained from :class:`asyncio.Queue`

    Example:
        >>> from __future__ import annotations
        >>>
        >>> from typing import Any
        >>>
        >>> import anyio
        >>>
        >>> from async_wrapper import Queue
        >>>
        >>>
        >>> async def aput(queue: Queue[Any], value: Any) -> None:
        >>>     async with queue:
        >>>         await queue.aput(value)
        >>>
        >>>
        >>> async def main() -> None:
        >>>     queue: Queue[Any] = Queue(10)
        >>>
        >>>     async with anyio.create_task_group() as task_group:
        >>>         async with queue.aputter:
        >>>             for i in range(10):
        >>>                 task_group.start_soon(aput, queue.clone(putter=True), i)
        >>>
        >>>     async with queue.agetter:
        >>>         result = {x async for x in queue}
        >>>
        >>>     assert result == set(range(10))
        >>>
        >>>
        >>> if __name__ == "__main__":
        >>>     anyio.run(main)
    """

    __slots__ = ("_putter", "_getter", "_close_putter", "_close_getter")

    _putter: MemoryObjectSendStream[ValueT]
    _getter: MemoryObjectReceiveStream[ValueT]

    if TYPE_CHECKING:

        def __init__(self, max_size: float | None = None) -> None:
            ...

    else:

        def __init__(
            self,
            max_size: float | None = None,
            *,
            _stream: tuple[
                MemoryObjectSendStream[ValueT],
                MemoryObjectReceiveStream[ValueT],
            ]
            | None = None,
        ) -> None:
            if _stream is None:
                self._putter, self._getter = create_memory_object_stream(
                    max_buffer_size=max_size or math.inf,
                )
            else:
                putter, getter = _stream
                if putter._closed or getter._closed:  # noqa: SLF001
                    raise QueueBrokenError("putter or getter is closed")
                if putter._state.buffer is not getter._state.buffer:  # noqa: SLF001
                    raise QueueBrokenError("putter and getter has diff buffer.")
                self._putter, self._getter = _stream

            self._close_putter: bool = True
            self._close_getter: bool = True

    @property
    def aputter(self) -> AsyncContextManager[Self]:
        """aclose putter only"""
        return self._as_aputter()

    @property
    def agetter(self) -> AsyncContextManager[Self]:
        """aclose getter only"""
        return self._as_agetter()

    @property
    def putter(self) -> ContextManager[Self]:
        """close putter only"""
        return self._as_putter()

    @property
    def getter(self) -> ContextManager[Self]:
        """close getter only"""
        return self._as_getter()

    @asynccontextmanager
    async def _as_aputter(self) -> AsyncGenerator[Self, None]:
        try:
            yield self
        finally:
            await self._putter.aclose()

    @asynccontextmanager
    async def _as_agetter(self) -> AsyncGenerator[Self, None]:
        try:
            yield self
        finally:
            await self._getter.aclose()

    @contextmanager
    def _as_putter(self) -> Generator[Self, None, None]:
        try:
            yield self
        finally:
            self._putter.close()

    @contextmanager
    def _as_getter(self) -> Generator[Self, None, None]:
        try:
            yield self
        finally:
            self._getter.close()

    @property
    def _closed(self) -> bool:
        return (not self._close_putter or self._putter._closed) and (  # noqa: SLF001
            not self._close_getter or self._getter._closed  # noqa: SLF001
        )

    def qsize(self) -> int:
        """number of items in the queue."""
        return len(self._getter._state.buffer)  # noqa: SLF001

    @property
    def maxsize(self) -> float:
        """number of items allowed in the queue."""
        return self._getter._state.max_buffer_size  # noqa: SLF001

    def empty(self) -> bool:
        """true if the queue is empty, false otherwise."""
        return self.qsize() <= 0

    def full(self) -> bool:
        """return true if there are maxsize items in the queue."""
        if self.maxsize == math.inf:
            return False
        return self.qsize() >= self.maxsize

    async def aget(self, *, timeout: float | None = None) -> ValueT:
        """remove and return an item from the queue.

        Args:
            timeout: error occurs when over timeout. Defaults to None.

        Returns:
            item from queue
        """
        with fail_after(timeout):
            return await self._aget()

    async def aput(self, value: ValueT, *, timeout: float | None = None) -> None:
        """put an item into the queue.

        Args:
            value: item
            timeout: error occurs when over timeout. Defaults to None.
        """
        with fail_after(timeout):
            await self._aput(value)

    async def _aget(self) -> ValueT:
        """remove and return an item from the queue."""
        try:
            return await self._getter.receive()
        except WouldBlock as exc:
            if self.empty():
                raise QueueEmptyError from exc
            raise QueueBrokenError from exc
        except (ClosedResourceError, BrokenResourceError) as exc:
            raise QueueBrokenError from exc

    async def _aput(self, value: ValueT) -> None:
        """put an item into the queue."""
        try:
            await self._putter.send(value)
        except WouldBlock as exc:
            if self.full():
                raise QueueFullError from exc
            raise QueueBrokenError from exc
        except (ClosedResourceError, BrokenResourceError) as exc:
            raise QueueBrokenError from exc

    def get(self) -> ValueT:
        """remove and return an item from the queue without blocking."""
        try:
            return self._getter.receive_nowait()
        except WouldBlock as exc:
            if self.empty():
                raise QueueEmptyError from exc
            raise QueueBrokenError from exc
        except (ClosedResourceError, BrokenResourceError) as exc:
            raise QueueBrokenError from exc

    def put(self, value: ValueT) -> None:
        """put an item into the queue without blocking."""
        try:
            self._putter.send_nowait(value)
        except WouldBlock as exc:
            if self.full():
                raise QueueFullError from exc
            raise QueueBrokenError from exc
        except (ClosedResourceError, BrokenResourceError) as exc:
            raise QueueBrokenError from exc

    async def aclose(self) -> None:
        """close the stream as async"""
        try:
            await self._aclose()
        except (ClosedResourceError, BrokenResourceError) as exc:
            raise QueueBrokenError from exc
        except ExceptionGroup as exc:
            if all(
                isinstance(error, (ClosedResourceError, BrokenResourceError))
                for error in exc.exceptions
            ):
                raise QueueBrokenError from exc
            raise

    def close(self) -> None:
        """close the stream as sync"""
        try:
            self._close()
        except (ClosedResourceError, BrokenResourceError) as exc:
            raise QueueBrokenError from exc

    async def _aclose(self) -> None:
        """close the stream as async"""
        async with create_task_group() as task_group:
            if self._close_getter:
                task_group.start_soon(self._getter.aclose)
            if self._close_putter:
                task_group.start_soon(self._putter.aclose)

    def _close(self) -> None:
        """close the stream as sync"""
        if self._close_getter:
            self._getter.close()
        if self._close_putter:
            self._putter.close()

    def clone(self, *, putter: bool = False, getter: bool = False) -> Queue[ValueT]:
        """create clone of this queue.

        Args:
            putter: if true, clone putter. Defaults to False.
            getter: if true, clone getter. Defaults to False.

        Returns:
            clone
        """
        try:
            return self._clone(putter=putter, getter=getter)
        except (ClosedResourceError, BrokenResourceError) as exc:
            raise QueueBrokenError from exc

    def _clone(self, *, putter: bool, getter: bool) -> Queue[ValueT]:
        """create clone of this queue"""
        if self._closed:
            raise QueueClosedError("the queue is already closed")
        if not putter and not getter:
            raise RuntimeError("putter and getter are None.")
        _putter = self._putter.clone() if putter else self._putter
        _getter = self._getter.clone() if getter else self._getter
        new = Queue(_stream=(_putter, _getter))  # type: ignore
        new._close_putter = putter  # noqa: SLF001
        new._close_getter = getter  # noqa: SLF001
        return new

    def statistics(self) -> MemoryObjectStreamStatistics:
        """return statstics from stream"""
        return self._getter._state.statistics()  # noqa: SLF001

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        try:
            self.close()
        finally:
            self._close_getter = True
            self._close_putter = True

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        try:
            await self.aclose()
        finally:
            self._close_getter = True
            self._close_putter = True

    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> ValueT:
        try:
            return await self.aget()
        except (
            EndOfStream,
            QueueEmptyError,
            QueueBrokenError,
            QueueClosedError,
        ) as exc:
            raise StopAsyncIteration from exc

    def __iter__(self) -> Self:
        return self

    def __next__(self) -> ValueT:
        try:
            return self.get()
        except (
            EndOfStream,
            QueueEmptyError,
            QueueBrokenError,
            QueueClosedError,
        ) as exc:
            raise StopIteration from exc

    def __len__(self) -> int:
        return self.qsize()

    def __repr__(self) -> str:
        max_size = "inf" if self.maxsize == math.inf else self.maxsize
        size = self.qsize()
        return f"<Queue: max={max_size}, size={size}>"


def create_queue(max_size: float | None = None) -> Queue[Any]:
    """create queue like :class:`asyncio.Queue`

    Args:
        max_size: queue size. Defaults to None.

    Returns:
        new :obj:`Queue` using :class:`anyio.abc.ObjectStream`
    """
    return Queue(max_size)
