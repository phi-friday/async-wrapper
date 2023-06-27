from __future__ import annotations

import sys
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

from typing_extensions import ParamSpec, override

from async_wrapper.taskgroup.base import BaseSoonWrapper, SoonValue

if sys.version_info < (3, 11):
    from aiotools.taskgroup import TaskGroup  # type: ignore
else:
    from asyncio.taskgroups import TaskGroup  # type: ignore


ValueT = TypeVar("ValueT")
ValueT_co = TypeVar("ValueT_co", covariant=True)
OtherValueT_co = TypeVar("OtherValueT_co", covariant=True)
ParamT = ParamSpec("ParamT")
OtherParamT = ParamSpec("OtherParamT")

__all__ = ["SoonWrapper", "wrap_soon", "get_taskgroup"]


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
            taskgroup: TaskGroup,
        ) -> SoonWrapper[OtherParamT, OtherValueT_co]:
            ...

    @override
    def __init__(
        self,
        func: Callable[ParamT, Awaitable[ValueT_co]],
        taskgroup: TaskGroup,
    ) -> None:
        super().__init__(func, taskgroup)

        def outer(
            result: SoonValue[ValueT_co],
        ) -> Callable[ParamT, None]:
            @wraps(self.func)
            def inner(*args: ParamT.args, **kwargs: ParamT.kwargs) -> None:
                partial_func = partial(self.func, *args, **kwargs)
                set_value_func = partial(_set_value, partial_func, result)
                taskgroup.create_task(set_value_func())

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


async def _set_value(
    func: Callable[[], Coroutine[Any, Any, ValueT]],
    value: SoonValue[ValueT],
) -> None:
    result = await func()
    value.value = result


wrap_soon = SoonWrapper
get_taskgroup = TaskGroup
