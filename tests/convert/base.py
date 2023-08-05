from __future__ import annotations

import inspect
import time
from typing import Final

import anyio
import pytest
from sniffio import current_async_library

from async_wrapper import async_to_sync, sync_to_async, toggle_func
from async_wrapper.convert._sync import _check_uvloop
from async_wrapper.convert.abc import AsyncToSync, SyncToAsync, Toggle


class BaseTest:
    epsilon: Final[float] = 0.1

    @classmethod
    def sync_to_async(cls) -> SyncToAsync:
        return sync_to_async

    @classmethod
    def async_to_sync(cls) -> AsyncToSync:
        return async_to_sync

    @classmethod
    def toggle(cls) -> Toggle:
        return toggle_func


class BaseSyncTest(BaseTest):
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

    @pytest.mark.anyio()
    @pytest.mark.parametrize("x", range(1, 4))
    async def test_async_to_sync_in_async(self, x: int):
        backend = current_async_library()
        sample = self.async_to_sync()(check_current_backend)
        use_uvloop = backend == "asyncio" and _check_uvloop()
        start = time.perf_counter()
        sample(x, self.epsilon, backend, use_uvloop=use_uvloop)
        end = time.perf_counter()
        term = end - start
        assert self.epsilon * x < term < self.epsilon * x + self.epsilon


@pytest.mark.anyio()
class BaseAsyncTest(BaseTest):
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


async def sample_async_func(x: int, epsilon: float) -> None:
    await anyio.sleep(epsilon * x)


async def check_current_backend(
    x: int,
    epsilon: float,
    backend: str,
    *,
    use_uvloop: bool,
) -> None:
    await anyio.sleep(epsilon * x)
    maybe = current_async_library()
    assert maybe == backend

    if use_uvloop:
        import asyncio

        import uvloop  # type: ignore

        policy = asyncio.get_event_loop_policy()
        assert isinstance(policy, uvloop.EventLoopPolicy)
