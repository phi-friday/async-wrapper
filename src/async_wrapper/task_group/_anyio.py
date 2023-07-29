from __future__ import annotations

from asyncio import create_task, wait
from functools import partial, wraps
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
from weakref import WeakSet

from typing_extensions import ParamSpec, Self, override

from async_wrapper.task_group.base import (
    BaseSoonWrapper,
    BaseTaskGroup,
    Semaphore,
    SoonValue,
)

try:
    from anyio.abc import TaskGroup as _TaskGroup  # type: ignore
except ImportError:
    from typing import Any as _TaskGroup

if TYPE_CHECKING:
    from asyncio import Task
    from types import TracebackType

    from anyio.abc import Semaphore as AnyioSemaphore  # type: ignore


ValueT = TypeVar("ValueT")
ValueT_co = TypeVar("ValueT_co", covariant=True)
OtherValueT_co = TypeVar("OtherValueT_co", covariant=True)
ParamT = ParamSpec("ParamT")
OtherParamT = ParamSpec("OtherParamT")

__all__ = ["SoonWrapper", "wrap_soon", "get_task_group", "get_semaphore_class"]


class TaskGroup(BaseTaskGroup):
    def __init__(self) -> None:
        self._task_group: _TaskGroup = _get_task_group()
        self._tasks: WeakSet[Task[Any]] = WeakSet()
        self._semaphore = None

    @override
    def start_soon(
        self,
        func: Callable[ParamT, Awaitable[ValueT_co]],
        *args: ParamT.args,
        **kwargs: ParamT.kwargs,
    ) -> SoonValue[ValueT_co]:
        value = SoonValue()
        wrapped = self._wrap(func, value)
        self._task_group.start_soon(partial(wrapped, **kwargs), *args)
        return value

    def _wrap(
        self,
        func: Callable[ParamT, Awaitable[ValueT_co]],
        value: SoonValue[ValueT_co],
    ) -> Callable[ParamT, Coroutine[None, None, None]]:
        @wraps(func)
        async def inner(*args: ParamT.args, **kwargs: ParamT.kwargs) -> None:
            awaitable = func(*args, **kwargs)
            coro = self(awaitable)
            task = create_task(coro)
            value.set_task_or_future(task)
            self.tasks.add(task)
            await task

        return inner

    @property
    @override
    def is_active(self) -> bool:
        return self._task_group._active  # type: ignore # noqa: SLF001

    @property
    @override
    def tasks(self) -> WeakSet[Task[Any]]:
        return self._tasks

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
    @override
    def __new__(
        cls,
        func: Callable[OtherParamT, Awaitable[OtherValueT_co]],
        task_group: TaskGroup,
        semaphore: Semaphore | None = None,
    ) -> SoonWrapper[OtherParamT, OtherValueT_co]:
        try:
            import anyio  # type: ignore # noqa: F401
        except ImportError as exc:
            raise ImportError("install extas anyio first") from exc

        return super().__new__(cls, func, task_group, semaphore)  # type: ignore

    @override
    def __call__(
        self,
        *args: ParamT.args,
        **kwargs: ParamT.kwargs,
    ) -> SoonValue[ValueT_co]:
        return self.task_group.start_soon(self.func, *args, **kwargs)

    @override
    def copy(self, semaphore: Semaphore | None = None) -> Self:
        if semaphore is None:
            semaphore = self.semaphore
        return SoonWrapper(self.func, self.task_group, semaphore)


def get_semaphore_class() -> type[AnyioSemaphore]:
    try:
        from anyio import Semaphore as _Semaphore  # type: ignore
    except ImportError as exc:
        raise ImportError("install extas anyio first") from exc
    return _Semaphore


def _get_task_group() -> _TaskGroup:
    try:
        from anyio import create_task_group  # type: ignore
    except ImportError as exc:
        raise ImportError("install extas anyio first") from exc
    return create_task_group()


wrap_soon = SoonWrapper
get_task_group = TaskGroup
