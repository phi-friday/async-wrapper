from __future__ import annotations

import inspect
import time

import anyio
import pytest

from async_wrapper import sync_to_async, toggle_func
from async_wrapper.convert.asynclib._thread import (
    sync_to_async as sync_to_async_as_thread,
)

EPSILON = 0.1


def test_correct_async_convertor():
    convertor = sync_to_async("thread")
    assert convertor is sync_to_async_as_thread


@pytest.mark.anyio()
@pytest.mark.parametrize("x", range(1, 4))
async def test_async_to_sync(x: int):
    @sync_to_async_as_thread
    def sample(x: int) -> None:
        time.sleep(EPSILON * x)

    start = time.perf_counter()
    await sample(x)
    end = time.perf_counter()
    term = end - start
    assert EPSILON * x < term < EPSILON * x + EPSILON


@pytest.mark.anyio()
@pytest.mark.parametrize("x", range(2, 5))
async def test_async_to_sync_gather(x: int):
    @sync_to_async_as_thread
    def sample(x: int) -> None:
        time.sleep(EPSILON * x)

    start = time.perf_counter()
    async with anyio.create_task_group() as task_group:
        for _ in range(x):
            task_group.start_soon(sample, 1)
    end = time.perf_counter()
    term = end - start
    assert EPSILON < term < EPSILON + EPSILON


@pytest.mark.anyio()
@pytest.mark.parametrize("x", range(2, 5))
async def test_toggle(x: int):
    @toggle_func
    def sample(x: int) -> None:
        time.sleep(EPSILON * x)

    assert inspect.iscoroutinefunction(sample)

    start = time.perf_counter()
    await sample(x)
    end = time.perf_counter()
    term = end - start
    assert EPSILON * x < term < EPSILON * x + EPSILON
