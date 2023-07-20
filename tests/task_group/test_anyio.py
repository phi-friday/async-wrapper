from __future__ import annotations

import time
from itertools import combinations

import pytest

from async_wrapper import (
    get_semaphore_class,
    get_task_group_factory,
    get_task_group_wrapper,
)
from async_wrapper.task_group._anyio import wrap_soon
from async_wrapper.task_group.base import SoonValue

pytest.importorskip("anyio")


try:
    import anyio  # type: ignore
except ImportError as exc:
    raise ImportError("install extas anyio first") from exc

EPSILON = 0.1


def test_correct_wrapper():
    wrapper = get_task_group_wrapper("anyio")
    assert wrapper is wrap_soon


@pytest.fixture(
    params=[
        pytest.param(("asyncio", {"use_uvloop": False}), id="anyio-asyncio"),
    ],
)
def anyio_backend(request):
    return request.param


@pytest.mark.anyio()
async def test_correct_task_group():
    factory = get_task_group_factory("anyio")
    task_group = factory()
    task_group_from_anyio = anyio.create_task_group()  # type: ignore
    assert isinstance(task_group, type(task_group_from_anyio))
    assert isinstance(task_group_from_anyio, type(task_group))


@pytest.mark.anyio()
@pytest.mark.parametrize("x", range(1, 4))
async def test_soon_value(x: int):
    wrapper = get_task_group_wrapper("anyio")
    factory = get_task_group_factory("anyio")

    async def sample_func(value: int) -> int:
        await anyio.sleep(EPSILON)  # type: ignore
        return value

    start = time.perf_counter()
    async with factory() as task_group:
        value = wrapper(sample_func, task_group)(x)
    end = time.perf_counter()
    term = end - start
    assert EPSILON < term < EPSILON + EPSILON

    assert isinstance(value, SoonValue)
    assert value.is_ready
    assert value.value == x


@pytest.mark.anyio()
@pytest.mark.parametrize(("x", "y"), combinations(range(1, 4), 2))
async def test_soon_value_many(x: int, y: int):
    wrapper = get_task_group_wrapper("anyio")
    factory = get_task_group_factory("anyio")

    async def sample_func(value: int) -> int:
        await anyio.sleep(EPSILON)  # type: ignore
        return value

    start = time.perf_counter()
    async with factory() as task_group:
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


@pytest.mark.anyio()
async def test_semaphore():
    wrapper = get_task_group_wrapper("anyio")
    factory = get_task_group_factory("anyio")
    semaphore = get_semaphore_class("anyio")
    sema = semaphore(2)

    async def sample_func() -> None:
        await anyio.sleep(EPSILON)  # type: ignore

    start = time.perf_counter()
    async with factory() as task_group:
        wrapped = wrapper(sample_func, task_group, sema)
        _ = [wrapped() for _ in range(3)]
    end = time.perf_counter()
    term = end - start
    assert EPSILON * 2 < term < EPSILON * 2 + EPSILON


@pytest.mark.asyncio()
async def test_overwrite_semaphore():
    wrapper = get_task_group_wrapper("anyio")
    factory = get_task_group_factory("anyio")
    semaphore = get_semaphore_class("anyio")
    sema = semaphore(2)
    new_sema = semaphore(3)

    async def sample_func() -> None:
        await anyio.sleep(EPSILON)  # type: ignore

    start = time.perf_counter()
    async with factory() as task_group:
        wrapped = wrapper(sample_func, task_group, sema)
        new_wrapped = wrapped.copy(new_sema)
        _ = [new_wrapped() for _ in range(3)]
    end = time.perf_counter()
    term = end - start
    assert EPSILON < term < EPSILON + EPSILON
