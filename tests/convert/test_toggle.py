from __future__ import annotations

from collections.abc import Callable
from typing import Any

import anyio
import pytest

from async_wrapper import toggle_func


def sample_sync_func(x: Any) -> Any:
    return x


async def sample_async_func(x: Any) -> Any:
    await anyio.sleep(0)
    return x


@pytest.mark.parametrize("func", [sample_sync_func, sample_async_func])
def test_toggle_twice(func: Callable[..., Any]):
    toggle = toggle_func(func)
    assert toggle is not func
    toggle = toggle_func(toggle)
    assert toggle is func
