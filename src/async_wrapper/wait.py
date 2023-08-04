from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Iterable, TypeVar

from anyio import Event
from typing_extensions import ParamSpec, Self, override

if TYPE_CHECKING:
    from anyio import EventStatistics
    from anyio.abc import TaskGroup


__all__ = ["Waiter", "wait_for"]

ValueT_co = TypeVar("ValueT_co", covariant=True)
ParamT = ParamSpec("ParamT")


class Waiter(Event):
    """wait wrapper

    how to use:
    >>> import anyio
    >>>
    >>> from async_wrapper.utils.wait import Waiter
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

    output:
    >>> $ poetry run python main.py
    >>> test: start
    >>> test2: start
    >>> test: end
    >>> test2: end
    """

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
            wait_for,
            self,
            partial(self._func, *self._args, **self._kwargs),
            name=name,
        )
        return self

    def __copy__(self) -> Self:
        return self.copy()

    def copy(self, *args: Any, **kwargs: Any) -> Self:
        """create new event

        Returns:
            new
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
    def set(self) -> Awaitable[Any]:
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


async def wait_for(
    event: Event | Iterable[Event],
    func: Callable[ParamT, Awaitable[ValueT_co]],
    *args: ParamT.args,
    **kwargs: ParamT.kwargs,
) -> ValueT_co:
    """wait func using event.

    Args:
        event: anyio event
        func: awaitable func

    Returns:
        func result

    how to use:
    >>> import anyio
    >>>
    >>> from async_wrapper.utils.wait import wait_for
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

    output:
    >>> $ poetry run python main.py
    >>> test: start
    >>> test2: start
    >>> test: end
    >>> test2: end
    """
    event = set(event) if not isinstance(event, Event) else (event,)
    try:
        return await func(*args, **kwargs)
    finally:
        for sub in event:
            sub.set()
