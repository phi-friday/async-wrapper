from __future__ import annotations

import sys

if sys.version_info < (3, 11):
    raise ModuleNotFoundError("asyncio.task_group >= 3.11")

from asyncio.taskgroups import TaskGroup  # type: ignore
from functools import partial, wraps
from typing import Any, Awaitable, Callable, Coroutine, Generic, TypeVar

from typing_extensions import ParamSpec, override

from async_wrapper.task_group.base import BaseSoonWrapper, SoonValue

ValueT = TypeVar("ValueT")
ParamT = ParamSpec("ParamT")

__all__ = ["SoonWrapper", "wrap_soon"]


class SoonWrapper(BaseSoonWrapper[TaskGroup, ParamT, ValueT], Generic[ParamT, ValueT]):
    @override
    def __init__(
        self,
        func: Callable[ParamT, Awaitable[ValueT]],
        task_group: TaskGroup,
    ) -> None:
        super().__init__(func, task_group)

        def outer(
            result: SoonValue[ValueT],
        ) -> Callable[ParamT, None]:
            @wraps(self.func)
            def inner(*args: ParamT.args, **kwargs: ParamT.kwargs) -> None:
                partial_func = partial(self.func, *args, **kwargs)
                set_value_func = partial(_set_value, partial_func, result)
                task_group.create_task(set_value_func())

            return inner

        self._func = outer

    @override
    def __call__(
        self,
        *args: ParamT.args,
        **kwargs: ParamT.kwargs,
    ) -> SoonValue[ValueT]:
        result: SoonValue[ValueT] = SoonValue()
        self._func(result)(*args, **kwargs)
        return result


async def _set_value(
    func: Callable[[], Coroutine[Any, Any, ValueT]],
    value: SoonValue[ValueT],
) -> None:
    result = await func()
    value.value = result


wrap_soon = SoonWrapper
