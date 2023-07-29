from __future__ import annotations

import sys
from asyncio import Semaphore as AsyncioSemaphore
from asyncio import wait
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    Coroutine,
    Generic,
    TypeVar,
    final,
)

from typing_extensions import ParamSpec, Self, override

from async_wrapper.task_group.base import (
    BaseSoonWrapper,
    BaseTaskGroup,
    Semaphore,
    SoonValue,
)

if sys.version_info < (3, 11):
    from aiotools.taskgroup import TaskGroup as _TaskGroup  # type: ignore
else:
    from asyncio.taskgroups import TaskGroup as _TaskGroup  # type: ignore

if TYPE_CHECKING:
    from asyncio import Task
    from types import TracebackType
    from weakref import WeakSet

ValueT = TypeVar("ValueT")
ValueT_co = TypeVar("ValueT_co", covariant=True)
OtherValueT_co = TypeVar("OtherValueT_co", covariant=True)
ParamT = ParamSpec("ParamT")
OtherParamT = ParamSpec("OtherParamT")

__all__ = ["SoonWrapper", "wrap_soon", "get_task_group", "get_semaphore_class"]


class TaskGroup(BaseTaskGroup):
    def __init__(self) -> None:
        self._task_group = _TaskGroup()

    @override
    def start_soon(
        self,
        func: Callable[ParamT, Coroutine[Any, Any, ValueT_co]],
        *args: ParamT.args,
        **kwargs: ParamT.kwargs,
    ) -> SoonValue[ValueT_co]:
        coro = func(*args, **kwargs)
        task = self._task_group.create_task(coro)
        return SoonValue(task_or_future=task)

    @property
    @override
    def is_active(self) -> bool:
        return self._task_group._entered  # noqa: SLF001

    @property
    @override
    def tasks(self) -> WeakSet[Task[Any]]:
        return self._task_group._tasks  # noqa: SLF001

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
            await wait(tasks)
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


def get_semaphore_class() -> type[AsyncioSemaphore]:
    return AsyncioSemaphore


wrap_soon = SoonWrapper
get_task_group = TaskGroup
