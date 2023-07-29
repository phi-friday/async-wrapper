from __future__ import annotations

from asyncio import create_task, ensure_future, wait
from itertools import chain
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
from weakref import WeakSet, WeakValueDictionary

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
    from asyncio import Future, Task
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
        self._futures: WeakSet[Future[Any]] = WeakSet()
        self._task_futures: WeakValueDictionary[
            Task[Any],
            Future[Any],
        ] = WeakValueDictionary()

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
        self._task_group.start_soon(self._as_task, future)
        return value

    def _as_future(
        self,
        func: Callable[ParamT, Coroutine[Any, Any, ValueT_co]],
        *args: ParamT.args,
        **kwargs: ParamT.kwargs,
    ) -> Future[ValueT_co]:
        coro = func(*args, **kwargs)
        future = ensure_future(coro)
        self._futures.add(future)
        return future

    async def _as_coro(self, future: Future[ValueT_co]) -> ValueT_co:
        return await future

    async def _as_task(self, future: Future[ValueT_co]) -> ValueT_co:
        coro = self._as_coro(future)
        task = create_task(coro)
        self._task_futures[task] = future
        return await task

    @property
    @override
    def is_active(self) -> bool:
        return self._task_group._active  # type: ignore # noqa: SLF001

    @property
    @override
    def tasks(self) -> WeakSet[Task[Any]]:
        return WeakSet(self._task_futures.keys())

    @property
    def futures(self) -> WeakSet[Future[Any]]:
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
        futures = tuple(self.futures)
        if tasks:
            await wait(chain(futures, tasks))
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
        wrapped = self.task_group._wrap(self.func, self.semaphore)  # noqa: SLF001
        return self.task_group.start_soon(wrapped, *args, **kwargs)

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
