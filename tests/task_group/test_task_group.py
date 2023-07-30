from __future__ import annotations

import time
from functools import partial
from itertools import combinations
from typing import Final

import anyio
import pytest

from async_wrapper import TaskGroupWrapper
from async_wrapper.task_group import SoonValue


@pytest.mark.anyio()
class TestTaskGroupWrapper:
    epsilon: Final[float] = 0.1

    @pytest.mark.parametrize("x", range(1, 4))
    async def test_soon_value(self, x: int):
        start = time.perf_counter()
        async with anyio.create_task_group() as task_group:
            wrapped = TaskGroupWrapper(task_group)
            func = wrapped.wrap(sample_func)
            value = func(x, self.epsilon)
        end = time.perf_counter()
        term = end - start
        assert self.epsilon < term < self.epsilon + self.epsilon

        assert isinstance(value, SoonValue)
        assert value.is_ready
        assert value.value == x

    @pytest.mark.parametrize(("x", "y"), tuple(combinations(range(1, 4), 2)))
    async def test_soon_value_many(self, x: int, y: int):
        start = time.perf_counter()
        async with anyio.create_task_group() as task_group:
            wrapped = TaskGroupWrapper(task_group)
            func = wrapped.wrap(sample_func)
            value_x = func(x, self.epsilon)
            value_y = func(y, self.epsilon)
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
        sema = anyio.Semaphore(2)

        start = time.perf_counter()
        async with anyio.create_task_group() as task_group:
            wrapped = TaskGroupWrapper(task_group)
            func = wrapped.wrap(sample_func_without_value, sema)
            _ = [func(self.epsilon) for _ in range(3)]
        end = time.perf_counter()
        term = end - start
        assert self.epsilon * 2 < term < self.epsilon * 2 + self.epsilon

    async def test_overwrite_semaphore(self):
        sema = anyio.Semaphore(2)
        new_sema = anyio.Semaphore(3)

        start = time.perf_counter()
        async with anyio.create_task_group() as task_group:
            wrapped = TaskGroupWrapper(task_group)
            func = wrapped.wrap(sample_func_without_value, sema)
            new_func = func.copy(new_sema)
            _ = [new_func(self.epsilon) for _ in range(3)]
        end = time.perf_counter()
        term = end - start
        assert self.epsilon < term < self.epsilon + self.epsilon

    async def test_wait_value(self):
        start = time.perf_counter()
        async with anyio.create_task_group() as task_group:
            wrapped = TaskGroupWrapper(task_group)
            func = wrapped.wrap(sample_func)
            value = func(1, self.epsilon)

            task_group.start_soon(value.future.wait, self.epsilon * 1_000_000)
            wrapped.start_soon(value.future.wait, self.epsilon * 1_000_000)
        end = time.perf_counter()
        term = end - start
        assert self.epsilon < term < self.epsilon + self.epsilon

    async def test_value_callback(self):
        origin = outer = 1

        def add(value: int) -> None:
            nonlocal outer
            outer += value

        start = time.perf_counter()
        async with anyio.create_task_group() as task_group:
            wrapped = TaskGroupWrapper(task_group)
            func = wrapped.wrap(sample_func)
            value = func(1, self.epsilon)
            value.add_done_callback(lambda v: add(v.value))
        end = time.perf_counter()
        term = end - start
        assert self.epsilon < term < self.epsilon + self.epsilon
        assert outer == origin + value.value


async def sample_func(value: int, sleep: float) -> int:
    await anyio.sleep(sleep)
    return value


sample_func_without_value = partial(sample_func, 0)
