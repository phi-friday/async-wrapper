from __future__ import annotations

import inspect
import time

import anyio
import pytest

from .base import BaseTest


@pytest.mark.anyio()
class TestAsync(BaseTest):
    @pytest.mark.parametrize("x", range(1, 4))
    async def test_sync_to_async(self, x: int):
        sample = self.sync_to_async()(sample_sync_func)
        start = time.perf_counter()
        await sample(x, self.epsilon)
        end = time.perf_counter()
        term = end - start
        assert self.epsilon * x < term < self.epsilon * x + self.epsilon

    @pytest.mark.parametrize("x", range(2, 5))
    async def test_sync_to_async_gather(self, x: int):
        sample = self.sync_to_async()(sample_sync_func)
        start = time.perf_counter()
        async with anyio.create_task_group() as task_group:
            for _ in range(x):
                task_group.start_soon(sample, 1, self.epsilon)
        end = time.perf_counter()
        term = end - start
        assert self.epsilon < term < self.epsilon + self.epsilon

    @pytest.mark.parametrize("x", range(2, 5))
    async def test_toggle(self, x: int):
        sample = self.toggle()(sample_sync_func)
        assert inspect.iscoroutinefunction(sample)
        start = time.perf_counter()
        await sample(x, self.epsilon)
        end = time.perf_counter()
        term = end - start
        assert self.epsilon * x < term < self.epsilon * x + self.epsilon


def sample_sync_func(x: int, epsilon: float) -> None:
    time.sleep(epsilon * x)
