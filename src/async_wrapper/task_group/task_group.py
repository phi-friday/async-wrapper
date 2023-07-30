from __future__ import annotations

from functools import partial, wraps
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Coroutine, Generic, TypeVar
from weakref import WeakSet

from anyio.abc import TaskGroup as _TaskGroup
from typing_extensions import ParamSpec, Self, override

from async_wrapper.task_group.future import Future
from async_wrapper.task_group.value import SoonValue

if TYPE_CHECKING:
    from types import TracebackType

    from anyio.abc import CancelScope, Semaphore


ValueT_co = TypeVar("ValueT_co", covariant=True)
OtherValueT_co = TypeVar("OtherValueT_co", covariant=True)
ParamT = ParamSpec("ParamT")
OtherParamT = ParamSpec("OtherParamT")


class TaskGroupWrapper(_TaskGroup):
    def __init__(self, task_group: _TaskGroup) -> None:
        self._task_group = task_group
        self._futures: WeakSet[Future[Any]] = WeakSet()

    @property
    def futures(self) -> WeakSet[Future[Any]]:
        """futures using wrapper"""
        return self._futures.copy()

    @property
    @override
    def cancel_scope(self) -> CancelScope:
        return self._task_group.cancel_scope

    @override
    async def spawn(
        self,
        func: Callable[..., Awaitable[Any]],
        *args: Any,
        name: Any = None,
    ) -> None:
        raise NotImplementedError

    @override
    def start_soon(
        self,
        func: Callable[..., Awaitable[Any]],
        *args: Any,
        name: Any = None,
    ) -> None:
        future = self._as_future(func, *args)
        return self._task_group.start_soon(future, name=name)

    @override
    async def start(
        self,
        func: Callable[..., Awaitable[Any]],
        *args: Any,
        name: Any = None,
    ) -> Any:
        raise NotImplementedError

    @override
    async def __aenter__(self) -> Self:
        await self._task_group.__aenter__()
        return self

    @override
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool | None:
        return await self._task_group.__aexit__(exc_type, exc_val, exc_tb)

    def wrap(
        self,
        func: Callable[ParamT, Awaitable[ValueT_co]],
        semaphore: Semaphore | None = None,
    ) -> SoonWrapper[ParamT, ValueT_co]:
        """wrap function to use in wrapper.

        func will return soon value.

        Args:
            func: target func
            semaphore: anyio semaphore. Defaults to None.

        Returns:
            wrapped func
        """
        return SoonWrapper(func, self, semaphore)

    def _as_future(
        self,
        func: Callable[ParamT, Awaitable[ValueT_co]],
        *args: ParamT.args,
        **kwargs: ParamT.kwargs,
    ) -> Future[ValueT_co]:
        coro = _as_coro(func, *args, **kwargs)
        future = Future(coro)
        self._futures.add(future)
        future.add_done_callback(partial(_remove_future, task_group=self))
        return future


class SoonWrapper(Generic[ParamT, ValueT_co]):
    def __init__(
        self,
        func: Callable[ParamT, Awaitable[ValueT_co]],
        task_group: _TaskGroup,
        semaphore: Semaphore | None = None,
    ) -> None:
        self.func = func
        self.task_group = task_group
        self.semaphore = semaphore
        self._wrapped = None

    def __call__(  # noqa: D102
        self,
        *args: ParamT.args,
        **kwargs: ParamT.kwargs,
    ) -> SoonValue[ValueT_co]:
        value: SoonValue[ValueT_co] = SoonValue()
        coro = self.wrapped(*args, **kwargs)
        future = Future(coro)
        value._set_future(future)  # noqa: SLF001
        self.task_group.start_soon(future)
        return value

    @property
    def wrapped(self) -> Callable[ParamT, Coroutine[Any, Any, ValueT_co]]:
        """wrapped func using semaphore"""
        if self._wrapped is not None:
            return self._wrapped

        @wraps(self.func)
        async def wrapped(*args: ParamT.args, **kwargs: ParamT.kwargs) -> ValueT_co:
            if self.semaphore is None:
                return await self.func(*args, **kwargs)
            async with self.semaphore:
                return await self.func(*args, **kwargs)

        self._wrapped = wrapped
        return wrapped

    def copy(self, semaphore: Semaphore | None = None) -> Self:
        """copy self.

        Args:
            semaphore: anyio semaphore.
                Defaults to None.
                if not None, overwrite.

        Returns:
            self
        """
        if semaphore is None:
            semaphore = self.semaphore
        return SoonWrapper(self.func, self.task_group, semaphore)


async def _as_coro(
    func: Callable[ParamT, Awaitable[ValueT_co]],
    *args: ParamT.args,
    **kwargs: ParamT.kwargs,
) -> ValueT_co:
    return await func(*args, **kwargs)


def _remove_future(future: Future[Any], task_group: TaskGroupWrapper) -> None:
    task_group._futures.remove(future)  # noqa: SLF001
