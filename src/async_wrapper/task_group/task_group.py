from __future__ import annotations

from contextlib import AsyncExitStack
from functools import partial, wraps
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Coroutine, Generic

from anyio import create_task_group as _create_task_group
from anyio.abc import TaskGroup as _TaskGroup
from typing_extensions import Concatenate, ParamSpec, Self, TypeVar, override

from async_wrapper.task_group.value import SoonValue

if TYPE_CHECKING:
    from types import TracebackType

    from anyio.abc import CancelScope, CapacityLimiter, Lock, Semaphore

ValueT = TypeVar("ValueT", infer_variance=True)
ParamT = ParamSpec("ParamT")

__all__ = ["TaskGroupWrapper", "create_task_group_wrapper"]


class TaskGroupWrapper(_TaskGroup):
    """
    wrap :class:`anyio.abc.TaskGroup`

    Example:
        >>> import anyio
        >>>
        >>> from async_wrapper import TaskGroupWrapper
        >>>
        >>>
        >>> async def test(x: int) -> int:
        >>>     await anyio.sleep(0.1)
        >>>     return x
        >>>
        >>>
        >>> async def main() -> None:
        >>>     async with anyio.create_task_group() as task_group:
        >>>         async with TaskGroupWrapper(task_group) as tg:
        >>>             func = tg.wrap(test)
        >>>             soon_1 = func(1)
        >>>             soon_2 = func(2)
        >>>
        >>>     assert soon_1.is_ready
        >>>     assert soon_2.is_ready
        >>>     assert soon_1.value == 1
        >>>     assert soon_2.value == 2
        >>>
        >>>
        >>> if __name__ == "__main__":
        >>>     anyio.run(main)
    """

    __slots__ = ("_task_group", "_active_self")

    def __init__(self, task_group: _TaskGroup) -> None:
        self._task_group = task_group
        self._active_self = False

    @property
    @override
    def cancel_scope(self) -> CancelScope:  # pyright: ignore[reportIncompatibleVariableOverride]
        return self._task_group.cancel_scope

    @override
    def start_soon(
        self, func: Callable[..., Awaitable[Any]], *args: Any, name: Any = None
    ) -> None:
        return self._task_group.start_soon(func, *args, name=name)

    @override
    async def start(
        self, func: Callable[..., Awaitable[Any]], *args: Any, name: Any = None
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
            try:
                return await self._task_group.__aexit__(exc_type, exc_val, exc_tb)
            finally:
                self._active_self = False
        return None

    def wrap(
        self,
        func: Callable[ParamT, Awaitable[ValueT]],
        semaphore: Semaphore | None = None,
        limiter: CapacityLimiter | None = None,
        lock: Lock | None = None,
    ) -> SoonWrapper[ParamT, ValueT]:
        """
        Wrap a function to be used within a wrapper.

        The wrapped function will return a value shortly.

        Args:
            func: The target function to be wrapped.
            semaphore: An :obj:`anyio.abc.Semaphore`. Defaults to None.
            limiter: An :obj:`anyio.abc.CapacityLimiter`. Defaults to None.
            lock: An :obj:`anyio.abc.Lock`. Defaults to None.

        Returns:
            The wrapped function.
        """
        return SoonWrapper(func, self, semaphore=semaphore, limiter=limiter, lock=lock)


class SoonWrapper(Generic[ParamT, ValueT]):
    """wrapped func using in :class:`TaskGroupWrapper`"""

    __slots__ = ("func", "task_group", "semaphore", "limiter", "lock", "_wrapped")

    def __init__(
        self,
        func: Callable[ParamT, Awaitable[ValueT]],
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

    def __call__(
        self, *args: ParamT.args, **kwargs: ParamT.kwargs
    ) -> SoonValue[ValueT]:
        value: SoonValue[ValueT] = SoonValue()
        wrapped = partial(self.wrapped, value, *args, **kwargs)
        self.task_group.start_soon(wrapped)
        return value

    @property
    def wrapped(
        self,
    ) -> Callable[Concatenate[SoonValue[ValueT], ParamT], Coroutine[Any, Any, ValueT]]:
        """wrapped func using semaphore"""
        if self._wrapped is not None:
            return self._wrapped

        @wraps(self.func)
        async def wrapped(
            value: SoonValue[ValueT], *args: ParamT.args, **kwargs: ParamT.kwargs
        ) -> ValueT:
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
            raise RuntimeError("never")  # pragma: no cover

        self._wrapped = wrapped
        return wrapped

    def copy(
        self,
        semaphore: Semaphore | None = None,
        limiter: CapacityLimiter | None = None,
        lock: Lock | None = None,
    ) -> Self:
        """
        Create a copy of this object.

        Args:
            semaphore: An :obj:`anyio.abc.Semaphore`.
                If provided, it will overwrite the existing semaphore. Defaults to None.
            limiter: An :obj:`anyio.abc.CapacityLimiter`.
                If provided, it will overwrite the existing limiter. Defaults to None.
            lock: An :obj:`anyio.abc.Lock`.
                If provided, it will overwrite the existing lock. Defaults to None.

        Returns:
            A copy of this object with optional overwritten components.
        """
        if semaphore is None:
            semaphore = self.semaphore
        if limiter is None:
            limiter = self.limiter
        if lock is None:
            lock = self.lock
        return SoonWrapper(  # type: ignore
            self.func, self.task_group, semaphore=semaphore, limiter=limiter, lock=lock
        )


def create_task_group_wrapper() -> TaskGroupWrapper:
    """
    create new task group wrapper

    Returns:
        new :obj:`TaskGroupWrapper`
    """
    return TaskGroupWrapper(_create_task_group())


def _is_active(task_group: _TaskGroup) -> bool:
    # trio, asyncio
    return task_group._active  # type: ignore # noqa: SLF001
