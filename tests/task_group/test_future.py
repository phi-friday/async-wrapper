from __future__ import annotations

import inspect
from contextlib import suppress
from typing import Any, Final, NoReturn

import anyio
import pytest

from async_wrapper.task_group import Future


class Error(Exception):
    ...


@pytest.mark.anyio()
class TestFuture:
    epsilon: Final[float] = 0.1

    @pytest.mark.parametrize("x", range(1, 4))
    async def test_future_await(self, x: int):
        coro = sample_func(x, self.epsilon)
        future = Future(coro)
        assert not future.is_begin
        result = await future

        assert result == x
        assert future.is_begin
        assert future.done
        assert future.is_ended
        assert future.result() == x

    @pytest.mark.parametrize("x", range(1, 4))
    async def test_future_to_coro(self, x: int):
        coro = sample_func(x, self.epsilon)
        future = Future(coro)
        assert not future.is_begin
        new_coro = future()
        result = await new_coro

        assert result == x
        assert future.is_begin
        assert future.done
        assert future.is_ended
        assert future.result() == x

    @pytest.mark.parametrize("x", range(1, 4))
    async def test_nested_future(self, x: int):
        coro = sample_func(x, self.epsilon)
        future = Future(coro)
        assert not future.is_begin
        new_coro = future()
        new_future = Future(new_coro)
        assert not new_future.is_begin
        result = await new_future

        assert result == x
        assert future.is_begin
        assert future.done
        assert future.is_ended
        assert future.result() == x

    async def test_add_done_callback(self):
        coro = sample_func(1, self.epsilon)
        future = Future(coro)
        values = []
        done = []
        ended = []
        future.add_done_callback(lambda x: values.append(x._coro_state))  # noqa: SLF001
        future.add_done_callback(lambda x: done.append(x.done))
        future.add_done_callback(lambda x: ended.append(x.is_ended))

        await future

        assert values
        value = values[0]
        assert isinstance(value, str)

        assert value == "CORO_CLOSED"
        assert inspect.getcoroutinestate(coro) == "CORO_CLOSED"

        assert done
        value = done[0]
        assert isinstance(value, bool)
        assert value is True

        assert ended
        value = ended[0]
        assert isinstance(value, bool)
        assert value is False

    async def test_add_final_callback(self):
        coro = sample_func(1, self.epsilon)
        future = Future(coro)
        values = []
        done = []
        ended = []
        future.add_final_callback(
            lambda x: values.append(x._coro_state),  # noqa: SLF001
        )
        future.add_final_callback(lambda x: done.append(x.done))
        future.add_final_callback(lambda x: ended.append(x.is_ended))

        await future

        assert values
        value = values[0]
        assert isinstance(value, str)

        assert value == "CORO_CLOSED"
        assert inspect.getcoroutinestate(coro) == "CORO_CLOSED"

        assert done
        value = done[0]
        assert isinstance(value, bool)
        assert value is True

        assert ended
        value = ended[0]
        assert isinstance(value, bool)
        assert value is True

    async def test_error_future(self):
        coro = error_func()
        future = Future(coro)

        with suppress(Error):
            await future

        assert future.is_ended
        assert future.cancelled
        exc = future.exception()
        assert exc is not None
        assert isinstance(exc, Error)


async def sample_func(value: int, sleep: float) -> int:
    await anyio.sleep(sleep)
    return value


async def error_func(*args: Any, **kwargs: Any) -> NoReturn:
    raise Error("error")
    error_func(*args, **kwargs)
