from __future__ import annotations

import asyncio
import time

import pytest

from async_wrapper import async_to_sync
from async_wrapper.convert.synclib._thread import (
    async_to_sync as async_to_sync_as_thread,
)

EPSILON = 0.1


def test_correct_sync_convertor():
    convertor = async_to_sync("thread")
    assert convertor is async_to_sync_as_thread


@pytest.mark.parametrize("x", range(1, 4))
def test_async_to_sync(x: int):
    @async_to_sync_as_thread
    async def sample(x: int) -> None:
        await asyncio.sleep(EPSILON * x)

    start = time.perf_counter()
    sample(x)
    end = time.perf_counter()
    term = end - start
    assert EPSILON * x < term < EPSILON * x + EPSILON
