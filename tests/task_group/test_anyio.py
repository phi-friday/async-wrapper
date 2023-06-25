from __future__ import annotations

import time
from itertools import combinations

import pytest

from async_wrapper import get_taskgroup_wrapper
from async_wrapper.task_group._anyio import wrap_soon
from async_wrapper.task_group.base import SoonValue

pytest.importorskip("anyio")


try:
    import anyio  # type: ignore
except (ImportError, ModuleNotFoundError) as exc:
    raise ImportError("install extas anyio first") from exc

EPSILON = 0.1


def test_correct_wrapper():
    wrapper = get_taskgroup_wrapper("anyio")
    assert wrapper is wrap_soon


@pytest.mark.asyncio()
@pytest.mark.parametrize("x", range(1, 4))
async def test_soon_value(x: int):
    wrapper = get_taskgroup_wrapper("anyio")

    async def sample_func(value: int) -> int:
        await anyio.sleep(EPSILON)  # type: ignore
        return value

    start = time.perf_counter()
    async with anyio.create_task_group() as task_group:  # type: ignore
        value = wrapper(sample_func, task_group)(x)
    end = time.perf_counter()
    term = end - start
    assert EPSILON < term < EPSILON + EPSILON

    assert isinstance(value, SoonValue)
    assert value.is_ready
    assert value.value == x


@pytest.mark.asyncio()
@pytest.mark.parametrize(("x", "y"), combinations(range(1, 4), 2))
async def test_soon_value_many(x: int, y: int):
    wrapper = get_taskgroup_wrapper("anyio")

    async def sample_func(value: int) -> int:
        await anyio.sleep(EPSILON)  # type: ignore
        return value

    start = time.perf_counter()
    async with anyio.create_task_group() as task_group:  # type: ignore
        wrapped = wrapper(sample_func, task_group)
        value_x = wrapped(x)
        value_y = wrapped(y)
    end = time.perf_counter()
    term = end - start
    assert EPSILON < term < EPSILON + EPSILON

    assert isinstance(value_x, SoonValue)
    assert isinstance(value_y, SoonValue)
    assert value_x.is_ready
    assert value_y.is_ready
    assert value_x.value == x
    assert value_y.value == y
