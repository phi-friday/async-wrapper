from __future__ import annotations

import asyncio
import time
from itertools import combinations
from typing import ClassVar, Final, Literal

import pytest

from async_wrapper import (
    get_semaphore_class,
    get_task_group_factory,
    get_task_group_wrapper,
)
from async_wrapper.task_group.base import SoonValue

EPSILON = 0.1


@pytest.fixture(
    params=[
        pytest.param(("asyncio", {"use_uvloop": False}), id="anyio-asyncio"),
    ],
)
def anyio_backend(request):
    return request.param


class BaseTest:
    epsilon: Final[float] = EPSILON
    backend: ClassVar[Literal["anyio", "asyncio"]]

    @pytest.mark.parametrize("x", range(1, 4))
    async def test_soon_value(self, x: int):
        wrapper = get_task_group_wrapper(self.backend)
        factory = get_task_group_factory(self.backend)

        async def sample_func(value: int) -> int:
            await asyncio.sleep(EPSILON)
            return value

        start = time.perf_counter()
        async with factory() as task_group:
            value = wrapper(sample_func, task_group)(x)  # type: ignore
        end = time.perf_counter()
        term = end - start
        assert EPSILON < term < EPSILON + EPSILON

        assert isinstance(value, SoonValue)
        assert value.is_ready
        assert value.value == x

    @pytest.mark.parametrize(("x", "y"), tuple(combinations(range(1, 4), 2)))
    async def test_soon_value_many(self, x: int, y: int):
        wrapper = get_task_group_wrapper(self.backend)
        factory = get_task_group_factory(self.backend)

        async def sample_func(value: int) -> int:
            await asyncio.sleep(EPSILON)
            return value

        start = time.perf_counter()
        async with factory() as task_group:
            wrapped = wrapper(sample_func, task_group)  # type: ignore
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

    async def test_semaphore(self):
        wrapper = get_task_group_wrapper(self.backend)
        factory = get_task_group_factory(self.backend)
        semaphore = get_semaphore_class(self.backend)
        sema = semaphore(2)

        async def sample_func() -> None:
            await asyncio.sleep(EPSILON)

        start = time.perf_counter()
        async with factory() as task_group:
            wrapped = wrapper(sample_func, task_group, sema)  # type: ignore
            _ = [wrapped() for _ in range(3)]
        end = time.perf_counter()
        term = end - start
        assert EPSILON * 2 < term < EPSILON * 2 + EPSILON

    async def test_overwrite_semaphore(self):
        wrapper = get_task_group_wrapper(self.backend)
        factory = get_task_group_factory(self.backend)
        semaphore = get_semaphore_class(self.backend)
        sema = semaphore(2)
        new_sema = semaphore(3)

        async def sample_func() -> None:
            await asyncio.sleep(EPSILON)

        start = time.perf_counter()
        async with factory() as task_group:
            wrapped = wrapper(sample_func, task_group, sema)  # type: ignore
            new_wrapped = wrapped.copy(new_sema)
            _ = [new_wrapped() for _ in range(3)]
        end = time.perf_counter()
        term = end - start
        assert EPSILON < term < EPSILON + EPSILON
