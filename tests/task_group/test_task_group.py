from __future__ import annotations

from itertools import combinations
from typing import Final

import anyio
import pytest
from anyio.lowlevel import checkpoint

from ..base import Timer  # noqa: TID252
from async_wrapper import TaskGroupWrapper, create_task_group_wrapper
from async_wrapper.task_group import SoonValue


@pytest.mark.anyio()
class TestTaskGroupWrapper:
    epsilon: Final[float] = 0.1

    @pytest.mark.parametrize("x", range(1, 4))
    async def test_soon_value(self, x: int):
        with Timer() as timer:
            async with anyio.create_task_group() as task_group:
                wrapped = TaskGroupWrapper(task_group)
                func = wrapped.wrap(sample_func)
                value = func(x)
        assert timer.term < self.epsilon + self.epsilon

        assert isinstance(value, SoonValue)
        assert value.is_ready
        assert value.value == x

    @pytest.mark.parametrize("x", range(1, 4))
    async def test_soon_value_direct(self, x: int):
        with Timer() as timer:
            async with create_task_group_wrapper() as task_group:
                func = task_group.wrap(sample_func)
                value = func(x)
        assert timer.term < self.epsilon + self.epsilon

        assert isinstance(value, SoonValue)
        assert value.is_ready
        assert value.value == x

    @pytest.mark.parametrize(("x", "y"), tuple(combinations(range(1, 4), 2)))
    async def test_soon_value_many(self, x: int, y: int):
        with Timer() as timer:
            async with anyio.create_task_group() as task_group:
                wrapped = TaskGroupWrapper(task_group)
                func = wrapped.wrap(sample_func)
                value_x = func(x)
                value_y = func(y)
        assert timer.term < self.epsilon + self.epsilon

        assert isinstance(value_x, SoonValue)
        assert isinstance(value_y, SoonValue)
        assert value_x.is_ready
        assert value_y.is_ready
        assert value_x.value == x
        assert value_y.value == y

    @pytest.mark.parametrize(("x", "y"), tuple(combinations(range(1, 4), 2)))
    async def test_soon_value_many_direct(self, x: int, y: int):
        with Timer() as timer:
            async with create_task_group_wrapper() as task_group:
                func = task_group.wrap(sample_func)
                value_x = func(x)
                value_y = func(y)
        assert timer.term < self.epsilon + self.epsilon

        assert isinstance(value_x, SoonValue)
        assert isinstance(value_y, SoonValue)
        assert value_x.is_ready
        assert value_y.is_ready
        assert value_x.value == x
        assert value_y.value == y

    async def test_semaphore(self):
        sema = anyio.Semaphore(2)

        with Timer() as timer:
            async with anyio.create_task_group() as task_group:
                wrapped = TaskGroupWrapper(task_group)
                func = wrapped.wrap(sample_sleep_func, sema)
                _ = [func(self.epsilon) for _ in range(3)]
        assert timer.term < self.epsilon * 2 + self.epsilon

    async def test_semaphore_direct(self):
        sema = anyio.Semaphore(2)

        with Timer() as timer:
            async with create_task_group_wrapper() as task_group:
                func = task_group.wrap(sample_sleep_func, sema)
                _ = [func(self.epsilon) for _ in range(3)]
        assert timer.term < self.epsilon * 2 + self.epsilon

    async def test_overwrite_semaphore(self):
        sema = anyio.Semaphore(2)
        new_sema = anyio.Semaphore(3)

        with Timer() as timer:
            async with anyio.create_task_group() as task_group:
                wrapped = TaskGroupWrapper(task_group)
                func = wrapped.wrap(sample_sleep_func, sema)
                new_func = func.copy(new_sema)
                _ = [new_func(self.epsilon) for _ in range(3)]
        assert timer.term < self.epsilon + self.epsilon

    async def test_overwrite_semaphore_direct(self):
        sema = anyio.Semaphore(2)
        new_sema = anyio.Semaphore(3)

        with Timer() as timer:
            async with create_task_group_wrapper() as task_group:
                func = task_group.wrap(sample_sleep_func, sema)
                new_func = func.copy(new_sema)
                _ = [new_func(self.epsilon) for _ in range(3)]
        assert timer.term < self.epsilon + self.epsilon

    async def test_limit(self):
        limit = anyio.CapacityLimiter(2)

        with Timer() as timer:
            async with anyio.create_task_group() as task_group:
                wrapped = TaskGroupWrapper(task_group)
                func = wrapped.wrap(sample_sleep_func, limiter=limit)
                _ = [func(self.epsilon) for _ in range(3)]
        assert timer.term < self.epsilon * 2 + self.epsilon

    async def test_limit_direct(self):
        limit = anyio.CapacityLimiter(2)

        with Timer() as timer:
            async with create_task_group_wrapper() as task_group:
                func = task_group.wrap(sample_sleep_func, limiter=limit)
                _ = [func(self.epsilon) for _ in range(3)]
        assert timer.term < self.epsilon * 2 + self.epsilon

    async def test_overwrite_limit(self):
        limit = anyio.CapacityLimiter(2)
        new_limit = anyio.CapacityLimiter(3)

        with Timer() as timer:
            async with anyio.create_task_group() as task_group:
                wrapped = TaskGroupWrapper(task_group)
                func = wrapped.wrap(sample_sleep_func, limiter=limit)
                new_func = func.copy(limiter=new_limit)
                _ = [new_func(self.epsilon) for _ in range(3)]
        assert timer.term < self.epsilon + self.epsilon

    async def test_overwrite_limit_direct(self):
        limit = anyio.CapacityLimiter(2)
        new_limit = anyio.CapacityLimiter(3)

        with Timer() as timer:
            async with create_task_group_wrapper() as task_group:
                func = task_group.wrap(sample_sleep_func, limiter=limit)
                new_func = func.copy(limiter=new_limit)
                _ = [new_func(self.epsilon) for _ in range(3)]
        assert timer.term < self.epsilon + self.epsilon

    async def test_lock(self):
        lock = anyio.Lock()

        with Timer() as timer:
            async with anyio.create_task_group() as task_group:
                wrapped = TaskGroupWrapper(task_group)
                func = wrapped.wrap(sample_sleep_func, lock=lock)
                _ = [func(self.epsilon) for _ in range(3)]
        assert timer.term < self.epsilon * 3 + self.epsilon

    async def test_lock_direct(self):
        lock = anyio.Lock()

        with Timer() as timer:
            async with create_task_group_wrapper() as task_group:
                func = task_group.wrap(sample_sleep_func, lock=lock)
                _ = [func(self.epsilon) for _ in range(3)]
        assert timer.term < self.epsilon * 3 + self.epsilon

    async def test_overwrite_lock(self):
        lock = anyio.Lock()
        new_lock = anyio.Lock()

        with Timer() as timer:
            async with anyio.create_task_group() as task_group:
                wrapped = TaskGroupWrapper(task_group)
                func = wrapped.wrap(sample_sleep_func, lock=lock)
                new_func = func.copy(lock=new_lock)
                _ = [func(self.epsilon) for _ in range(2)]
                _ = new_func(self.epsilon)
        assert timer.term < self.epsilon * 2 + self.epsilon

    async def test_overwrite_lock_direct(self):
        lock = anyio.Lock()
        new_lock = anyio.Lock()

        with Timer() as timer:
            async with create_task_group_wrapper() as task_group:
                func = task_group.wrap(sample_sleep_func, lock=lock)
                new_func = func.copy(lock=new_lock)
                _ = [func(self.epsilon) for _ in range(2)]
                _ = new_func(self.epsilon)
        assert timer.term < self.epsilon * 2 + self.epsilon


async def sample_func(value: int) -> int:
    await checkpoint()
    return value


async def sample_sleep_func(value: float) -> None:
    await anyio.sleep(value)
