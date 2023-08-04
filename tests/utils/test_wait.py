from __future__ import annotations

from typing import Any

import anyio
import pytest

from async_wrapper.task_group import SoonValue
from async_wrapper.utils.wait import Waiter, wait_for


@pytest.mark.anyio()
async def test_waiter():
    soon = SoonValue()

    async with anyio.create_task_group() as task_group:
        event = Waiter(sample_func, 0.1, 1, soon)(task_group)
        task_group.start_soon(sample_wait, event, 2, soon)

    assert event.is_set()
    assert soon.is_ready
    assert soon.value == 1


@pytest.mark.anyio()
async def test_waiter_reuse():
    soon = SoonValue()
    new_soon = SoonValue()

    async with anyio.create_task_group() as task_group:
        event = Waiter(sample_func, 0.1)(task_group)
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
    soon = SoonValue()

    async with anyio.create_task_group() as task_group:
        event = Waiter(sample_func, 0.1)
        new_event = event.copy(0.1, 3, soon)(task_group)
        task_group.start_soon(sample_wait, new_event, 2, soon)

    assert not event.is_set()
    assert new_event.is_set()
    assert soon.is_ready
    assert soon.value == 3


@pytest.mark.anyio()
async def test_wait_for():
    event = anyio.Event()
    soon = SoonValue()
    async with anyio.create_task_group() as task_group:
        task_group.start_soon(wait_for, event, sample_func, 0.1, 1, soon)
        task_group.start_soon(sample_wait, event, 2, soon)

    assert event.is_set()
    assert soon.is_ready
    assert soon.value == 1


@pytest.mark.anyio()
async def test_wait_many():
    events = [anyio.Event() for _ in range(10)]
    soon = SoonValue()
    async with anyio.create_task_group() as task_group:
        task_group.start_soon(wait_for, events, sample_func, 0.1, 1, soon)
        for event in events:
            task_group.start_soon(sample_wait, event, 2, soon)

    for event in events:
        assert event.is_set()
    assert soon.is_ready
    assert soon.value == 1


async def sample_wait(event: anyio.Event, value: Any, soon: SoonValue[Any]) -> None:
    await event.wait()
    if not soon.is_ready:
        soon._value = value  # noqa: SLF001


async def sample_func(
    sleep: float,
    value: Any = None,
    soon: SoonValue[Any] | None = None,
) -> None:
    await anyio.sleep(sleep)
    if soon is not None and not soon.is_ready:
        await anyio.sleep(sleep)
        soon._value = value  # noqa: SLF001
