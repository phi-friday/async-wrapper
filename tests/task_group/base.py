from __future__ import annotations

import time
from functools import partial
from itertools import combinations
from typing import ClassVar, Final, Literal

import anyio
import pytest

from async_wrapper import (
    get_semaphore_class,
    get_task_group_factory,
    get_task_group_wrapper,
)
from async_wrapper.task_group.base import (
    BaseSoonWrapper,
    BaseTaskGroup,
    Semaphore,
    SoonValue,
    TaskGroupFactory,
)


class BaseTest:
    epsilon: Final[float] = 0.1
    backend: ClassVar[Literal["anyio"]]

    @classmethod
    def wrapper(cls) -> type[BaseSoonWrapper]:
        return get_task_group_wrapper(cls.backend)

    @classmethod
    def factory(cls) -> TaskGroupFactory[BaseTaskGroup]:
        return get_task_group_factory(cls.backend)

    @classmethod
    def semaphore(cls) -> type[Semaphore]:
        return get_semaphore_class(cls.backend)

    @pytest.mark.parametrize("x", range(1, 4))
    async def test_soon_value(self, x: int):
        start = time.perf_counter()
        async with self.factory()() as task_group:
            value = self.wrapper()(sample_func, task_group)(x, self.epsilon)
        end = time.perf_counter()
        term = end - start
        assert self.epsilon < term < self.epsilon + self.epsilon

        assert isinstance(value, SoonValue)
        assert value.is_ready
        assert value.value == x

    @pytest.mark.parametrize(("x", "y"), tuple(combinations(range(1, 4), 2)))
    async def test_soon_value_many(self, x: int, y: int):
        start = time.perf_counter()
        async with self.factory()() as task_group:
            wrapped = self.wrapper()(sample_func, task_group)
            value_x = wrapped(x, self.epsilon)
            value_y = wrapped(y, self.epsilon)
        end = time.perf_counter()
        term = end - start
        assert self.epsilon < term < self.epsilon + self.epsilon

        assert isinstance(value_x, SoonValue)
        assert isinstance(value_y, SoonValue)
        assert value_x.is_ready
        assert value_y.is_ready
        assert value_x.value == x
        assert value_y.value == y

    async def test_semaphore(self):
        wrapper = get_task_group_wrapper(self.backend)
        factory = get_task_group_factory(self.backend)
        semaphore = get_semaphore_class(self.backend)
        sema = semaphore(2)

        start = time.perf_counter()
        async with factory() as task_group:
            wrapped = wrapper(
                sample_func_without_value,
                task_group,  # type: ignore
                sema,
            )
            _ = [wrapped(self.epsilon) for _ in range(3)]
        end = time.perf_counter()
        term = end - start
        assert self.epsilon * 2 < term < self.epsilon * 2 + self.epsilon

    async def test_overwrite_semaphore(self):
        wrapper = get_task_group_wrapper(self.backend)
        factory = get_task_group_factory(self.backend)
        semaphore = get_semaphore_class(self.backend)
        sema = semaphore(2)
        new_sema = semaphore(3)

        start = time.perf_counter()
        async with factory() as task_group:
            wrapped = wrapper(
                sample_func_without_value,
                task_group,  # type: ignore
                sema,
            )
            new_wrapped = wrapped.copy(new_sema)
            _ = [new_wrapped(self.epsilon) for _ in range(3)]
        end = time.perf_counter()
        term = end - start
        assert self.epsilon < term < self.epsilon + self.epsilon


async def sample_func(value: int, sleep: float) -> int:
    await anyio.sleep(sleep)
    return value


sample_func_without_value = partial(sample_func, 0)
