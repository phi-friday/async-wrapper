from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Iterable

from anyio import EndOfStream, Event, create_memory_object_stream, create_task_group
from typing_extensions import ParamSpec, Self, TypeVar, override

from async_wrapper.exception import PendingError

if TYPE_CHECKING:
    from types import TracebackType

    from anyio import EventStatistics
    from anyio.abc import CancelScope, TaskGroup
    from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream


__all__ = ["Waiter", "Completed", "wait_for"]

ValueT = TypeVar("ValueT", infer_variance=True)
ParamT = ParamSpec("ParamT")


class Waiter(Event):
    """
    wait wrapper

    Example:
        >>> import anyio
        >>>
        >>> from async_wrapper import Waiter
        >>>
        >>>
        >>> async def test() -> None:
        >>>     print("test: start")
        >>>     await anyio.sleep(1)
        >>>     print("test: end")
        >>>
        >>>
        >>> async def test2(event: anyio.Event) -> None:
        >>>     print("test2: start")
        >>>     await event.wait()
        >>>     print("test2: end")
        >>>
        >>>
        >>> async def main() -> None:
        >>>     async with anyio.create_task_group() as task_group:
        >>>         event = Waiter(test)(task_group)
        >>>         task_group.start_soon(test2, event)
        >>>
        >>>
        >>> if __name__ == "__main__":
        >>>     anyio.run(main)
        $ poetry run python main.py
        test: start
        test2: start
        test: end
        test2: end
    """

    __slots__ = ("_event", "_func", "_args", "_kwargs")

    _event: Event

    def __init__(
        self,
        func: Callable[ParamT, Awaitable[Any]],
        *args: ParamT.args,
        **kwargs: ParamT.kwargs,
    ) -> None:
        self._func = func
        self._args = args
        self._kwargs = kwargs

    def __call__(self, task_group: TaskGroup, *, name: Any = None) -> Self:
        """start soon in task group"""
        task_group.start_soon(
            wait_for, self, partial(self._func, *self._args, **self._kwargs), name=name
        )
        return self

    def __copy__(self) -> Self:
        return self.copy()

    def copy(self, *args: Any, **kwargs: Any) -> Self:
        """
        create new event

        Returns:
            new :obj:`Waiter`
        """
        if not args:
            args = tuple(self._args)
        if not kwargs:
            kwargs = self._kwargs.copy()
        return Waiter(self._func, *args, **kwargs)  # type: ignore

    @override
    def __new__(
        cls,
        func: Callable[ParamT, Awaitable[Any]],
        *args: ParamT.args,
        **kwargs: ParamT.kwargs,
    ) -> Self:
        new = object.__new__(cls)
        new._event = super().__new__(cls)  # noqa: SLF001
        return new

    @override
    def set(self) -> None:
        return self._event.set()

    @override
    def is_set(self) -> bool:
        return self._event.is_set()

    @override
    async def wait(self) -> None:
        return await self._event.wait()

    @override
    def statistics(self) -> EventStatistics:
        return self._event.statistics()


class Completed:
    """
    like :func:`asyncio.as_completed`

    Example:
        >>> from __future__ import annotations
        >>>
        >>> import anyio
        >>>
        >>> from async_wrapper import Completed
        >>>
        >>>
        >>> async def test(
        >>>     x: int,
        >>>     sleep: float,
        >>>     result: list[int] | None = None,
        >>> ) -> int:
        >>>     print(f"[{x}] test: start")
        >>>     await anyio.sleep(sleep)
        >>>     print(f"[{x}] test: end")
        >>>     if result is not None:
        >>>         result.append(x)
        >>>     return x
        >>>
        >>>
        >>> async def main() -> None:
        >>>     result: list[int] = []
        >>>     async with anyio.create_task_group() as task_group:
        >>>         task_group.start_soon(test, 1, 1, result)
        >>>         async with Completed(task_group) as completed:
        >>>             completed.start_soon(None, test, 2, 0.2)
        >>>             completed.start_soon(None, test, 3, 0.1)
        >>>             completed.start_soon(None, test, 4, 0.3)
        >>>
        >>>             result.extend([value async for value in completed])
        >>>
        >>>     assert result == [3, 2, 4, 1]
        >>>
        >>>     result = []
        >>>     async with anyio.create_task_group() as task_group:
        >>>         task_group.start_soon(test, 1, 1, result)
        >>>         async with Completed() as completed:
        >>>             completed.start_soon(task_group, test, 2, 0.2)
        >>>             completed.start_soon(task_group, test, 3, 0.1)
        >>>             completed.start_soon(task_group, test, 4, 0.3)
        >>>
        >>>             result.extend([value async for value in completed])
        >>>
        >>>     assert result == [3, 2, 4, 1]
        >>>
        >>>
        >>> if __name__ == "__main__":
        >>>     anyio.run(main)
    """

    __slots__ = ("_events", "__setter", "__getter", "__task_group")

    def __init__(self, task_group: TaskGroup | None = None) -> None:
        self._events: dict[Waiter, MemoryObjectReceiveStream[Any]] = {}
        self.__setter: MemoryObjectSendStream[Waiter] | None = None
        self.__getter: MemoryObjectReceiveStream[Waiter] | None = None
        self.__task_group: TaskGroup | None = task_group

    @property
    def _is_active(self) -> bool:
        return self.__setter is not None

    @property
    def _setter(self) -> MemoryObjectSendStream[Waiter]:
        if self.__setter is None:
            raise PendingError("enter first")
        return self.__setter

    @property
    def _getter(self) -> MemoryObjectReceiveStream[Waiter]:
        if self.__getter is None:
            raise PendingError("enter first")
        return self.__getter

    def _task_group(self, task_group: TaskGroup | None) -> TaskGroup:
        if self.__task_group is None:
            if task_group is None:
                raise ValueError("there is no task group")
            return task_group

        if task_group is None:
            return self.__task_group

        if task_group is not self.__task_group:
            raise ValueError("diff task groups")

        return task_group

    def start_soon(
        self,
        task_group: TaskGroup | None,
        func: Callable[..., Awaitable[Any]],
        *args: Any,
        name: Any = None,
    ) -> None:
        """
        Start a coroutine in a task group,
        similar to :meth:`anyio.abc.TaskGroup.start_soon`.

        If a task group is already provided,
        the task_group parameter should be the same object.

        Args:
            task_group: An :class:`anyio.abc.TaskGroup`. Defaults to None.
            func: The target coroutine function.
            *args: The arguments to pass to the coroutine function.
            name: The name used in :meth:`anyio.abc.TaskGroup.start_soon`.
                Defaults to None.
        """  # noqa: D205
        if not self._is_active:
            raise PendingError("enter first")
        task_group = self._task_group(task_group)
        waiter, getter = _create_waiter(func, *args)
        waiter(task_group, name=name)
        self._events[waiter] = getter

    async def _shutdown(self) -> None:
        async with create_task_group() as task_group:
            task_group.start_soon(self._setter.aclose)
            task_group.start_soon(self._getter.aclose)
            for getter in self._events.values():
                if not getter._closed:  # noqa: SLF001
                    task_group.start_soon(getter.aclose)

    async def _anext(self) -> Any:
        if not self._events:
            raise EndOfStream

        async with create_task_group() as task_group:
            for event in self._events:
                task_group.start_soon(
                    _wait_waiter, event, task_group.cancel_scope, self
                )

        event = await self._getter.receive()
        getter = self._events.pop(event)
        async with getter:
            return await getter.receive()

    async def __aenter__(self) -> Self:
        self.__setter, self.__getter = create_memory_object_stream(1)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        try:
            await self._shutdown()
        finally:
            self.__setter = None
            self.__getter = None

    def __aiter__(self) -> Self:
        if self.__setter is None:
            raise PendingError("enter first")
        return self

    async def __anext__(self) -> Any:
        try:
            return await self._anext()
        except EndOfStream as exc:
            raise StopAsyncIteration from exc


async def wait_for(
    event: Event | Iterable[Event],
    func: Callable[ParamT, Awaitable[ValueT]],
    *args: ParamT.args,
    **kwargs: ParamT.kwargs,
) -> ValueT:
    """
    Wait for an event before executing an awaitable function.

    like :func:`asyncio.wait_for`

    Args:
        event: An :obj:`anyio.Event` or an iterable of events.
        func: An awaitable function to be executed.
        *args: The arguments to pass to the awaitable function.
        **kwargs: The keyword arguments to pass to the awaitable function.

    Returns:
        The result of the executed function.

    Example:
        >>> import anyio
        >>>
        >>> from async_wrapper import wait_for
        >>>
        >>>
        >>> async def test() -> None:
        >>>     print("test: start")
        >>>     await anyio.sleep(1)
        >>>     print("test: end")
        >>>
        >>>
        >>> async def test2(event: anyio.Event) -> None:
        >>>     print("test2: start")
        >>>     await event.wait()
        >>>     print("test2: end")
        >>>
        >>>
        >>> async def main() -> None:
        >>>     event = anyio.Event()
        >>>     async with anyio.create_task_group() as task_group:
        >>>         task_group.start_soon(wait_for, event, test)
        >>>         task_group.start_soon(test2, event)
        >>>
        >>>
        >>> if __name__ == "__main__":
        >>>     anyio.run(main)
        $ poetry run python main.py
        test: start
        test2: start
        test: end
        test2: end
    """
    event = set(event) if not isinstance(event, Event) else (event,)
    try:
        return await func(*args, **kwargs)
    finally:
        for sub in event:
            sub.set()


async def _wait_waiter(
    waiter: Waiter, scope: CancelScope, completed: Completed
) -> None:
    await waiter.wait()
    completed._setter.send_nowait(waiter)  # noqa: SLF001
    scope.cancel()


async def _intercept_value(
    setter: MemoryObjectSendStream[Any],
    getter: MemoryObjectReceiveStream[Any],
    func: Callable[..., Awaitable[Any]],
    *args: Any,
) -> None:
    async with setter:
        result = await func(*args)
        if not getter._closed:  # noqa: SLF001
            await setter.send(result)


def _create_waiter(
    func: Callable[..., Awaitable[Any]], *args: Any
) -> tuple[Waiter, MemoryObjectReceiveStream[Any]]:
    setter: MemoryObjectSendStream[Any]
    getter: MemoryObjectReceiveStream[Any]
    setter, getter = create_memory_object_stream(1)
    waiter = Waiter(_intercept_value, setter, getter, func, *args)

    return waiter, getter
