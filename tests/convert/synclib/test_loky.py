from __future__ import annotations

import asyncio
import inspect
import time

import pytest

from async_wrapper import async_to_sync, toggle_func
from async_wrapper.convert.synclib._loky import (
    async_to_sync as async_to_sync_as_loky,
)

pytest.importorskip("loky")

EPSILON = 0.3


def test_correct_sync_convertor():
    convertor = async_to_sync("loky")
    assert convertor is async_to_sync_as_loky


@pytest.mark.parametrize("x", range(1, 4))
def test_async_to_sync(x: int):
    @async_to_sync_as_loky
    async def sample(x: int) -> None:
        await asyncio.sleep(EPSILON * x)

    start = time.perf_counter()
    sample(x)
    end = time.perf_counter()
    term = end - start
    assert EPSILON * x < term < EPSILON * x + EPSILON


@pytest.mark.parametrize("x", range(2, 5))
def test_toggle(x: int):
    @toggle_func
    async def sample(x: int) -> None:
        await asyncio.sleep(EPSILON * x)

    assert not inspect.iscoroutinefunction(sample)

    start = time.perf_counter()
    sample(x)
    end = time.perf_counter()
    term = end - start
    assert EPSILON * x < term < EPSILON * x + EPSILON
