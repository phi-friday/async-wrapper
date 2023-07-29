from __future__ import annotations

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

from anyio import Semaphore as _Semaphore
from anyio import create_task_group
from typing_extensions import ParamSpec, Self, override

from async_wrapper.task_group.base import (
    BaseSoonWrapper,
    BaseTaskGroup,
    Future,
    Semaphore,
    SoonValue,
)

if TYPE_CHECKING:
    from types import TracebackType

    from anyio.abc import Semaphore as AnyioSemaphore  # type: ignore
    from anyio.abc import TaskGroup as _TaskGroup


ValueT = TypeVar("ValueT")
ValueT_co = TypeVar("ValueT_co", covariant=True)
OtherValueT_co = TypeVar("OtherValueT_co", covariant=True)
ParamT = ParamSpec("ParamT")
OtherParamT = ParamSpec("OtherParamT")

__all__ = ["SoonWrapper", "wrap_soon", "get_task_group", "get_semaphore_class"]


class CancelError(Exception):
    ...


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
        value._set_future(future)  # noqa: SLF001
        self._task_group.start_soon(_as_coro, future)
        return value

    def _as_future(
        self,
        func: Callable[ParamT, Coroutine[Any, Any, ValueT_co]],
        *args: ParamT.args,
        **kwargs: ParamT.kwargs,
    ) -> Future[ValueT_co]:
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
            await self.wait(tasks)
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


async def _as_coro(future: Future[ValueT_co]) -> ValueT_co:
    return await future


wrap_soon = SoonWrapper
get_task_group = TaskGroup
