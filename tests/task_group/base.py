from __future__ import annotations

import asyncio
import time
from functools import partial
from itertools import combinations
from typing import ClassVar, Final, Literal

import pytest

from async_wrapper import (
    get_semaphore_class,
    get_task_group_factory,
    get_task_group_wrapper,
)
from async_wrapper.task_group.base import SoonValue


class BaseTest:
    epsilon: Final[float] = 0.1
    backend: ClassVar[Literal["anyio", "asyncio"]]

    @pytest.mark.parametrize("x", range(1, 4))
    async def test_soon_value(self, x: int):
        wrapper = get_task_group_wrapper(self.backend)
        factory = get_task_group_factory(self.backend)

        start = time.perf_counter()
        async with factory() as task_group:
            value = wrapper(sample_func, task_group)(x, self.epsilon)  # type: ignore
        end = time.perf_counter()
        term = end - start
        assert self.epsilon < term < self.epsilon + self.epsilon

        assert isinstance(value, SoonValue)
        assert value.is_ready
        assert value.value == x
        assert value.result() == x

    @pytest.mark.parametrize(("x", "y"), tuple(combinations(range(1, 4), 2)))
    async def test_soon_value_many(self, x: int, y: int):
        wrapper = get_task_group_wrapper(self.backend)
        factory = get_task_group_factory(self.backend)

        start = time.perf_counter()
        async with factory() as task_group:
            wrapped = wrapper(sample_func, task_group)  # type: ignore
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
        assert value_x.result() == x
        assert value_y.result() == y

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
    await asyncio.sleep(sleep)
    return value


@pytest.fixture(
    params=[
        pytest.param(("asyncio", {"use_uvloop": False}), id="anyio-asyncio"),
    ],
)
def anyio_backend(request):
    return request.param


sample_func_without_value = partial(sample_func, 0)
