from __future__ import annotations

import inspect
import time

import anyio
import pytest

from .base import BaseTest


class TestSync(BaseTest):
    @pytest.mark.parametrize("x", range(1, 4))
    def test_async_to_sync(self, x: int):
        sample = self.async_to_sync()(sample_async_func)
        start = time.perf_counter()
        sample(x, self.epsilon)
        end = time.perf_counter()
        term = end - start
        assert self.epsilon * x < term < self.epsilon * x + self.epsilon

    @pytest.mark.parametrize("x", range(2, 5))
    def test_toggle(self, x: int):
        sample = self.toggle()(sample_async_func)
        assert not inspect.iscoroutinefunction(sample)
        start = time.perf_counter()
        sample(x, self.epsilon)
        end = time.perf_counter()
        term = end - start
        assert self.epsilon * x < term < self.epsilon * x + self.epsilon


async def sample_async_func(x: int, epsilon: float) -> None:
    await anyio.sleep(epsilon * x)
