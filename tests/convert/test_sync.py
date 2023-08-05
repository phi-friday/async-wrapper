from __future__ import annotations

import inspect

import anyio
import pytest
from sniffio import current_async_library

from ..base import Timer  # noqa: TID252
from .base import BaseTest
from async_wrapper.convert._sync import _check_uvloop


class TestSync(BaseTest):
    @pytest.mark.parametrize("x", range(1, 4))
    def test_async_to_sync(self, x: int):
        sample = self.async_to_sync()(sample_async_func)
        with Timer() as timer:
            sample(x, self.epsilon)
        assert self.epsilon * x < timer.term < self.epsilon * x + self.epsilon

    @pytest.mark.parametrize("x", range(2, 5))
    def test_toggle(self, x: int):
        sample = self.toggle()(sample_async_func)
        assert not inspect.iscoroutinefunction(sample)
        with Timer() as timer:
            sample(x, self.epsilon)
        assert self.epsilon * x < timer.term < self.epsilon * x + self.epsilon

    @pytest.mark.anyio()
    @pytest.mark.parametrize("x", range(1, 4))
    async def test_async_to_sync_in_async(self, x: int):
        backend = current_async_library()
        sample = self.async_to_sync()(check_current_backend)
        use_uvloop = backend == "asyncio" and _check_uvloop()
        with Timer() as timer:
            sample(x, self.epsilon, backend, use_uvloop=use_uvloop)
        assert self.epsilon * x < timer.term < self.epsilon * x + self.epsilon


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
