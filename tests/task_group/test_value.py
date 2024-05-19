from __future__ import annotations

from typing import Any

import pytest
from anyio import Event, create_task_group
from anyio.lowlevel import checkpoint

from async_wrapper.exception import PendingError
from async_wrapper.task_group import SoonValue
from async_wrapper.task_group.value import Pending


def test_value_pending():
    value: SoonValue[Any] = SoonValue()
    assert not value.is_ready
    assert value._value is Pending  # noqa: SLF001
    with pytest.raises(PendingError, match=""):
        _ = value.value


@pytest.mark.parametrize("x", range(4))
def test_value_setattr(x: int):
    value: SoonValue[Any] = SoonValue()
    assert not value.is_ready
    assert value._value is Pending  # noqa: SLF001

    value._value = x  # noqa: SLF001
    maybe = value.value
    assert maybe == x


@pytest.mark.anyio()
@pytest.mark.parametrize("x", range(4))
async def test_value_setattr_async(x: int):
    value: SoonValue[Any] = SoonValue()
    assert not value.is_ready

    event = Event()

    async def set_value() -> None:
        await checkpoint()
        value._value = x  # noqa: SLF001
        event.set()

    async def check_value() -> None:
        await event.wait()
        assert value.is_ready
        maybe = value.value
        assert maybe == x

    async with create_task_group() as task_group:
        task_group.start_soon(check_value)
        task_group.start_soon(set_value)

    assert value.is_ready
    maybe = value.value
    assert maybe == x


def test_value_repr():
    value: SoonValue[Any] = SoonValue()
    value._value = 1  # noqa: SLF001
    assert value.is_ready
    expected = "<SoonValue: status=done>"
    assert repr(value) == expected


def test_value_repr_pending():
    value: SoonValue[Any] = SoonValue()
    assert not value.is_ready
    expected = "<SoonValue: status=pending>"
    assert repr(value) == expected
