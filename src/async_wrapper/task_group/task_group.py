from __future__ import annotations

from contextlib import AsyncExitStack
from functools import partial, wraps
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Coroutine, Generic, TypeVar

from anyio.abc import TaskGroup as _TaskGroup
from typing_extensions import Concatenate, ParamSpec, Self, override

from async_wrapper.task_group.value import SoonValue

if TYPE_CHECKING:
    from types import TracebackType

    from anyio.abc import CancelScope, CapacityLimiter, Lock, Semaphore

ValueT_co = TypeVar("ValueT_co", covariant=True)
OtherValueT_co = TypeVar("OtherValueT_co", covariant=True)
ParamT = ParamSpec("ParamT")
OtherParamT = ParamSpec("OtherParamT")


class TaskGroupWrapper(_TaskGroup):
    def __init__(self, task_group: _TaskGroup) -> None:
        self._task_group = task_group
        self._active_self = False

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
        return self._task_group.start_soon(_as_coro, func, *args, name=name)

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
        if _is_active(self._task_group):
            return self
        await self._task_group.__aenter__()
        self._active_self = True
        return self

    @override
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool | None:
        if self._active_self:
            return await self._task_group.__aexit__(exc_type, exc_val, exc_tb)
        return None

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


class SoonWrapper(Generic[ParamT, ValueT_co]):
    def __init__(  # noqa: PLR0913
        self,
        func: Callable[ParamT, Awaitable[ValueT_co]],
        task_group: _TaskGroup,
        semaphore: Semaphore | None = None,
        limiter: CapacityLimiter | None = None,
        lock: Lock | None = None,
    ) -> None:
        self.func = func
        self.task_group = task_group
        self.semaphore = semaphore
        self.limiter = limiter
        self.lock = lock

        self._wrapped = None

    def __call__(  # noqa: D102
        self,
        *args: ParamT.args,
        **kwargs: ParamT.kwargs,
    ) -> SoonValue[ValueT_co]:
        value: SoonValue[ValueT_co] = SoonValue()
        wrapped = partial(self.wrapped, value, *args, **kwargs)
        self.task_group.start_soon(wrapped)
        return value

    @property
    def wrapped(
        self,
    ) -> Callable[
        Concatenate[SoonValue[ValueT_co], ParamT],
        Coroutine[Any, Any, ValueT_co],
    ]:
        """wrapped func using semaphore"""
        if self._wrapped is not None:
            return self._wrapped

        @wraps(self.func)
        async def wrapped(
            value: SoonValue[ValueT_co],
            *args: ParamT.args,
            **kwargs: ParamT.kwargs,
        ) -> ValueT_co:
            async with AsyncExitStack() as stack:
                if self.semaphore is not None:
                    await stack.enter_async_context(self.semaphore)
                if self.limiter is not None:
                    await stack.enter_async_context(self.limiter)
                if self.lock is not None:
                    await stack.enter_async_context(self.lock)

                result = await self.func(*args, **kwargs)
                value._value = result  # noqa: SLF001
                return result
            raise RuntimeError("never")

        self._wrapped = wrapped
        return wrapped

    def copy(
        self,
        semaphore: Semaphore | None = None,
        limiter: CapacityLimiter | None = None,
        lock: Lock | None = None,
    ) -> Self:
        """copy self.

        Args:
            semaphore: anyio semaphore.
                Defaults to None.
                if not None, overwrite.
            limiter: anyio capacity limiter.
                Defaults to None.
                if not None, overwrite.
            lock: anyio lock.
                Defaults to None.
                if not None, overwrite.

        Returns:
            self
        """
        if semaphore is None:
            semaphore = self.semaphore
        if limiter is None:
            limiter = self.limiter
        if lock is None:
            lock = self.lock
        return SoonWrapper(
            self.func,
            self.task_group,
            semaphore=semaphore,
            limiter=limiter,
            lock=lock,
        )


async def _as_coro(
    func: Callable[ParamT, Awaitable[ValueT_co]],
    *args: ParamT.args,
    **kwargs: ParamT.kwargs,
) -> ValueT_co:
    return await func(*args, **kwargs)


def _is_active(task_group: _TaskGroup) -> bool:
    # trio, asyncio
    return task_group._active  # type: ignore # noqa: SLF001
