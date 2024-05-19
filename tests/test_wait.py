from __future__ import annotations

from functools import partial
from typing import Any

import anyio
import pytest
from anyio.lowlevel import checkpoint

from async_wrapper import Completed, Waiter, wait_for
from async_wrapper.exception import PendingError
from async_wrapper.task_group import SoonValue

TIC = 0.01


@pytest.mark.anyio()
async def test_waiter():
    soon: SoonValue[Any] = SoonValue()

    async with anyio.create_task_group() as task_group:
        event = Waiter(sample_func, 1, soon)(task_group)
        task_group.start_soon(sample_wait, event, 2, soon)

    assert event.is_set()
    assert soon.is_ready
    assert soon.value == 1


@pytest.mark.anyio()
async def test_waiter_reuse():
    soon: SoonValue[Any] = SoonValue()
    new_soon: SoonValue[Any] = SoonValue()

    async with anyio.create_task_group() as task_group:
        event = Waiter(sample_func)(task_group)
        task_group.start_soon(sample_wait, event, 1, soon)
        new_event = event.copy()(task_group)
        task_group.start_soon(sample_wait, event, 2, new_soon)

    assert event.is_set()
    assert soon.is_ready
    assert soon.value == 1
    assert new_event.is_set()
    assert new_soon.is_ready
    assert new_soon.value == 2


@pytest.mark.anyio()
async def test_waiter_reuse_overwrite():
    soon: SoonValue[Any] = SoonValue()

    async with anyio.create_task_group() as task_group:
        event = Waiter(sample_func)
        new_event = event.copy(3, soon)(task_group)
        task_group.start_soon(sample_wait, new_event, 2, soon)

    assert not event.is_set()
    assert new_event.is_set()
    assert soon.is_ready
    assert soon.value == 3


@pytest.mark.anyio()
async def test_wait_for():
    event = anyio.Event()
    soon: SoonValue[Any] = SoonValue()
    async with anyio.create_task_group() as task_group:
        task_group.start_soon(wait_for, event, partial(sample_func, 1, soon))
        task_group.start_soon(sample_wait, event, 2, soon)

    assert event.is_set()
    assert soon.is_ready
    assert soon.value == 1


@pytest.mark.anyio()
async def test_wait_many():
    events = [anyio.Event() for _ in range(10)]
    soon: SoonValue[Any] = SoonValue()
    async with anyio.create_task_group() as task_group:
        task_group.start_soon(wait_for, events, partial(sample_func, 1, soon))
        for event in events:
            task_group.start_soon(sample_wait, event, 2, soon)

    for event in events:
        assert event.is_set()
    assert soon.is_ready
    assert soon.value == 1


@pytest.mark.anyio()
async def test_completed_with_task_group():
    result: list[int] = []
    async with anyio.create_task_group() as task_group:
        task_group.start_soon(sample_func2, 1, 3, result)
        async with Completed(task_group) as completed:
            completed.start_soon(None, sample_func2, 2, 2)
            completed.start_soon(None, sample_func2, 3, 1)

            result.extend([value async for value in completed])

    assert result == [3, 2, 1]


@pytest.mark.anyio()
async def test_completed_without_task_group():
    result: list[int] = []
    async with anyio.create_task_group() as task_group:
        task_group.start_soon(sample_func2, 1, 3, result)
        async with Completed() as completed:
            completed.start_soon(task_group, sample_func2, 2, 2)
            completed.start_soon(task_group, sample_func2, 3, 1)

            result.extend([value async for value in completed])

    assert result == [3, 2, 1]


@pytest.mark.anyio()
async def test_completed_overwrite_task_group():
    result: list[int] = []
    async with anyio.create_task_group() as task_group:
        task_group.start_soon(sample_func2, 1, 3, result)
        async with Completed(task_group) as completed:
            completed.start_soon(task_group, sample_func2, 2, 2)
            completed.start_soon(task_group, sample_func2, 3, 1)

            result.extend([value async for value in completed])

    assert result == [3, 2, 1]


@pytest.mark.anyio()
async def test_completed_overwrite_diff_task_group():
    async with anyio.create_task_group() as task_group:
        async with Completed(task_group) as completed:
            async with anyio.create_task_group() as new_tg:
                with pytest.raises(ValueError, match="diff task groups"):
                    completed.start_soon(new_tg, sample_func2, 2, 2)


@pytest.mark.anyio()
async def test_completed_no_task_group():
    async with anyio.create_task_group():
        async with Completed() as completed:
            with pytest.raises(ValueError, match="there is no task group"):
                completed.start_soon(None, sample_func2, 2, 2)


@pytest.mark.anyio()
async def test_completed_without_enter():
    async with anyio.create_task_group() as task_group:
        completed = Completed(task_group)
        with pytest.raises(PendingError, match="enter first"):
            completed.start_soon(None, sample_func2, 2, 2)


@pytest.mark.anyio()
async def test_completed_after_exit():
    async with anyio.create_task_group() as task_group:
        async with Completed(task_group) as completed:
            completed.start_soon(None, sample_func2, 1, 1)
        with pytest.raises(PendingError, match="enter first"):
            _ = [value async for value in completed]


async def sample_wait(event: anyio.Event, value: Any, soon: SoonValue[Any]) -> None:
    await event.wait()
    if not soon.is_ready:
        soon._value = value  # noqa: SLF001


async def sample_func(value: Any = None, soon: SoonValue[Any] | None = None) -> None:
    await checkpoint()
    if soon is not None and not soon.is_ready:
        await checkpoint()
        soon._value = value  # noqa: SLF001


async def sample_func2(value: int, sleep: int, result: list[int] | None = None) -> int:
    await anyio.sleep(TIC * sleep)
    if result is not None:
        result.append(value)
    return value
