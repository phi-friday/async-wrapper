from __future__ import annotations

import asyncio
import inspect
import time

import pytest

from async_wrapper import sync_to_async, toggle_func
from async_wrapper.convert.asynclib._joblib import (
    sync_to_async as sync_to_async_as_joblib,
)

pytest.importorskip("joblib")

EPSILON = 0.3


def test_correct_async_convertor():
    convertor = sync_to_async("joblib")
    assert convertor is sync_to_async_as_joblib


@pytest.mark.asyncio()
@pytest.mark.parametrize("x", range(1, 4))
async def test_async_to_sync(x: int):
    @sync_to_async_as_joblib
    def sample(x: int) -> None:
        time.sleep(EPSILON * x)

    start = time.perf_counter()
    await sample(x)
    end = time.perf_counter()
    term = end - start
    assert EPSILON * x < term < EPSILON * x + EPSILON


@pytest.mark.asyncio()
@pytest.mark.parametrize("x", range(2, 5))
async def test_async_to_sync_gather(x: int):
    @sync_to_async_as_joblib
    def sample(x: int) -> None:
        time.sleep(EPSILON * x)

    coro = asyncio.gather(*(sample(1) for _ in range(x)))
    start = time.perf_counter()
    await coro
    end = time.perf_counter()
    term = end - start
    assert EPSILON < term < EPSILON + EPSILON


@pytest.mark.asyncio()
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
