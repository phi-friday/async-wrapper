from __future__ import annotations

from contextlib import AsyncExitStack
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

from typing_extensions import ParamSpec, Self, override

from async_wrapper.task_group.base import BaseSoonWrapper, Semaphore, SoonValue

try:
    from anyio.abc import TaskGroup  # type: ignore
except ImportError:
    from typing import Any as TaskGroup

if TYPE_CHECKING:
    from anyio.abc import Semaphore as AnyioSemaphore  # type: ignore


ValueT = TypeVar("ValueT")
ValueT_co = TypeVar("ValueT_co", covariant=True)
OtherValueT_co = TypeVar("OtherValueT_co", covariant=True)
ParamT = ParamSpec("ParamT")
OtherParamT = ParamSpec("OtherParamT")

__all__ = ["SoonWrapper", "wrap_soon", "get_task_group", "get_semaphore_class"]


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
    def __init__(
        self,
        func: Callable[ParamT, Awaitable[ValueT_co]],
        task_group: TaskGroup,
        semaphore: Semaphore | None = None,
    ) -> None:
        super().__init__(func, task_group, semaphore)

        def outer(
            result: SoonValue[ValueT_co],
        ) -> Callable[ParamT, None]:
            @wraps(self.func)
            def inner(*args: ParamT.args, **kwargs: ParamT.kwargs) -> None:
                partial_func = partial(self.func, *args, **kwargs)
                set_value_func = partial(_set_value, partial_func, result, semaphore)
                task_group.start_soon(set_value_func)

            return inner

        self._func = outer

    @override
    def __call__(
        self,
        *args: ParamT.args,
        **kwargs: ParamT.kwargs,
    ) -> SoonValue[ValueT_co]:
        result: SoonValue[ValueT_co] = SoonValue()
        self._func(result)(*args, **kwargs)
        return result

    @override
    def copy(self, semaphore: Semaphore | None = None) -> Self:
        if semaphore is None:
            semaphore = self.semaphore
        return SoonWrapper(self.func, self.task_group, semaphore)


def get_task_group() -> TaskGroup:
    try:
        from anyio import create_task_group  # type: ignore
    except ImportError as exc:
        raise ImportError("install extas anyio first") from exc
    return create_task_group()


def get_semaphore_class() -> type[AnyioSemaphore]:
    try:
        from anyio import Semaphore as _Semaphore  # type: ignore
    except ImportError as exc:
        raise ImportError("install extas anyio first") from exc
    return _Semaphore


async def _set_value(
    func: Callable[[], Coroutine[Any, Any, ValueT]],
    value: SoonValue[ValueT],
    semaphore: Semaphore | None,
) -> None:
    async with AsyncExitStack() as stack:
        if semaphore is not None:
            await stack.enter_async_context(semaphore)
        result = await func()
    value.value = result


wrap_soon = SoonWrapper
