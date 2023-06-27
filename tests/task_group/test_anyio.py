from __future__ import annotations

import time
from itertools import combinations

import pytest

from async_wrapper import get_taskgroup_factory, get_taskgroup_wrapper
from async_wrapper.taskgroup._anyio import wrap_soon
from async_wrapper.taskgroup.base import SoonValue

pytest.importorskip("anyio")


try:
    import anyio  # type: ignore
except ImportError as exc:
    raise ImportError("install extas anyio first") from exc

EPSILON = 0.1


def test_correct_wrapper():
    wrapper = get_taskgroup_wrapper("anyio")
    assert wrapper is wrap_soon


@pytest.mark.asyncio()
async def test_correct_taskgroup():
    factory = get_taskgroup_factory("anyio")
    taskgroup = factory()
    taskgroup_from_anyio = anyio.create_task_group()  # type: ignore
    assert isinstance(taskgroup, type(taskgroup_from_anyio))
    assert isinstance(taskgroup_from_anyio, type(taskgroup))


@pytest.mark.asyncio()
@pytest.mark.parametrize("x", range(1, 4))
async def test_soon_value(x: int):
    wrapper = get_taskgroup_wrapper("anyio")
    factory = get_taskgroup_factory("anyio")

    async def sample_func(value: int) -> int:
        await anyio.sleep(EPSILON)  # type: ignore
        return value

    start = time.perf_counter()
    async with factory() as taskgroup:
        value = wrapper(sample_func, taskgroup)(x)
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
    factory = get_taskgroup_factory("anyio")

    async def sample_func(value: int) -> int:
        await anyio.sleep(EPSILON)  # type: ignore
        return value

    start = time.perf_counter()
    async with factory() as taskgroup:
        wrapped = wrapper(sample_func, taskgroup)
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
