from __future__ import annotations

import inspect
from functools import partial
from itertools import product
from typing import Any, Callable

import anyio
import pytest
from typing_extensions import TypeVar

from .base import Timer
from async_wrapper.exception import PipeAlreadyDisposedError
from async_wrapper.pipe import Pipe

pytestmark = pytest.mark.anyio

ValueT = TypeVar("ValueT", infer_variance=True)

EPSILON: float = 0.01


class CustomDisposable:
    def __init__(self, dispose: Callable[[], Any] | None = None) -> None:
        self.value = None
        self.disposed = False
        self._dispose = dispose

    async def next(self, value: Any) -> Any:
        await anyio.sleep(0)
        self.value = value
        return value

    async def dispose(self) -> Any:
        await anyio.sleep(0)
        self.disposed = True

        if self._dispose is not None:
            value = self._dispose()
            if inspect.isawaitable(value):
                await value


async def as_tuple(value: ValueT) -> tuple[ValueT]:
    await anyio.sleep(0)
    return (value,)


async def as_str(value: Any) -> str:
    await anyio.sleep(0)
    return str(value)


async def return_self(value: ValueT) -> ValueT:
    await anyio.sleep(0)
    return value


def use_value():
    result = None

    async def getter() -> Any:
        await anyio.sleep(0)
        return result

    async def setter(value: Any) -> None:
        nonlocal result
        await anyio.sleep(0)
        result = value

    return getter, setter


async def test_next():
    flag: bool = False

    def check_hit() -> None:
        if flag is not True:
            raise ValueError("no-hit")

    async def hit(value: Any) -> None:  # noqa: ARG001
        nonlocal flag
        await anyio.sleep(0)
        flag = True

    pipe = Pipe(hit)
    await pipe.next(1)

    check_hit()


@pytest.mark.parametrize(
    ("x", "func_and_type"), product(range(1, 4), ((as_tuple, tuple), (as_str, str)))
)
async def test_subscribe(x: int, func_and_type: tuple[Any, Any]):
    pipe: Pipe[int, Any] = Pipe(func_and_type[0])
    getter, setter = use_value()
    pipe.subscribe(setter)

    await pipe.next(x)
    result = await getter()

    assert isinstance(result, func_and_type[1])

    if func_and_type[1] is tuple:
        assert result[0] == x
    elif func_and_type[1] is str:
        assert result == str(x)


@pytest.mark.parametrize("x", range(1, 4))
async def test_subscribe_interface(x: int):
    pipe: Pipe[int, int] = Pipe(return_self)
    disposable = CustomDisposable()
    pipe.subscribe(disposable)

    assert disposable.value is None
    await pipe.next(x)

    assert isinstance(disposable.value, int)
    assert disposable.value == x


@pytest.mark.parametrize("x", range(1, 4))
async def test_subscribe_many(x: int):
    size = 10
    check: list[Any] = [False] * size

    async def hit(value: Any, index: int) -> None:
        nonlocal check
        await anyio.sleep(0)
        check[index] = value

    pipe = Pipe(as_str)
    for index in range(size):
        pipe.subscribe(partial(hit, index=index))

    await pipe.next(x)
    assert check == [str(x)] * size


@pytest.mark.parametrize("x", range(1, 4))
async def test_subscribe_chain(x: int):
    pipe1: Pipe[int, int] = Pipe(return_self)
    pipe2: Pipe[int, tuple[int]] = Pipe(as_tuple)
    pipe3: Pipe[Any, str] = Pipe(as_str)

    getter, setter = use_value()
    pipe1.subscribe(pipe2)
    pipe2.subscribe(pipe3)
    pipe3.subscribe(setter)

    await pipe1.next(x)
    result = await getter()

    assert isinstance(result, str)
    assert result == str((x,))


async def test_empty_dispose():
    pipe: Pipe[Any, Any] = Pipe(return_self)
    disposable = CustomDisposable()
    pipe.subscribe(disposable)

    assert disposable.disposed is False
    await pipe.dispose()
    assert disposable.disposed is True


async def test_dispose():
    flag: bool = False

    async def hit() -> None:
        nonlocal flag
        await anyio.sleep(0)
        flag = True

    pipe: Pipe[Any, Any] = Pipe(return_self, dispose=hit)
    disposable = CustomDisposable()
    pipe.subscribe(disposable)

    assert disposable.disposed is False
    assert flag is False
    await pipe.dispose()
    assert disposable.disposed is True
    assert flag is True


async def test_dispose_many():
    size = 10
    check: list[Any] = [False] * size

    async def hit(index: int) -> None:
        nonlocal check
        await anyio.sleep(0)
        check[index] = True

    pipe: Pipe[Any, Any] = Pipe(return_self)
    for index in range(size):
        disposable = CustomDisposable(dispose=partial(hit, index=index))
        pipe.subscribe(disposable)

    assert all(x is False for x in check)
    await pipe.dispose()
    assert all(x is True for x in check)


async def test_dispose_chain():
    pipe: Pipe[Any, Any] = Pipe(return_self)
    disposable1 = Pipe(return_self)
    disposable2 = CustomDisposable()

    pipe.subscribe(disposable1)
    disposable1.subscribe(disposable2)

    assert disposable1.is_disposed is False
    assert disposable2.disposed is False
    await pipe.dispose()

    assert disposable1.is_disposed is True
    assert disposable2.disposed is True


async def test_dispose_only_once():
    count = 0

    async def hit() -> None:
        nonlocal count
        await anyio.sleep(0)
        count += 1

    pipe = Pipe(return_self, dispose=hit)
    assert count == 0
    for _ in range(10):
        await pipe.dispose()
    assert count == 1


async def test_do_not_dispose():
    flag: bool = False

    async def hit() -> None:
        nonlocal flag
        await anyio.sleep(0)
        flag = True

    pipe = Pipe(return_self)
    disposable = CustomDisposable(dispose=hit)
    pipe.subscribe(disposable, dispose=False)

    assert disposable.disposed is False
    await pipe.dispose()
    assert disposable.disposed is False


async def test_semaphore():
    size = 3
    check: list[Any] = [False] * size

    async def hit(value: Any, index: int) -> None:
        nonlocal check
        await anyio.sleep(EPSILON)
        check[index] = value

    sema_value = 2
    sema = anyio.Semaphore(sema_value)
    pipe = Pipe(as_str, context={"semaphore": sema})
    for index in range(size):
        pipe.subscribe(partial(hit, index=index))

    with Timer() as timer:
        await pipe.next(1)

    q = size // sema_value + 1
    assert EPSILON * q < timer.term < EPSILON * q + EPSILON


async def test_limit():
    size = 3
    check: list[Any] = [False] * size

    async def hit(value: Any, index: int) -> None:
        nonlocal check
        await anyio.sleep(EPSILON)
        check[index] = value

    limit_value = 2
    limit = anyio.CapacityLimiter(limit_value)
    pipe = Pipe(as_str, context={"limiter": limit})
    for index in range(size):
        pipe.subscribe(partial(hit, index=index))

    with Timer() as timer:
        await pipe.next(1)

    q = size // limit_value + 1
    assert EPSILON * q < timer.term < EPSILON * q + EPSILON


async def test_lock():
    size = 3
    check: list[Any] = [False] * size

    async def hit(value: Any, index: int) -> None:
        nonlocal check
        await anyio.sleep(EPSILON)
        check[index] = value

    lock = anyio.Lock()
    pipe = Pipe(as_str, context={"lock": lock})
    for index in range(size):
        pipe.subscribe(partial(hit, index=index))

    with Timer() as timer:
        await pipe.next(1)

    assert EPSILON * size < timer.term < EPSILON * size + EPSILON


async def test_next_after_disposed():
    flag: bool = False

    async def hit(value: Any) -> None:  # noqa: ARG001
        nonlocal flag
        await anyio.sleep(0)
        flag = True

    pipe = Pipe(hit)
    await pipe.dispose()
    assert pipe.is_disposed is True

    with pytest.raises(PipeAlreadyDisposedError, match="pipe already disposed"):
        await pipe.next(1)


async def test_subscribe_after_disposed():
    pipe = Pipe(return_self)
    await pipe.dispose()
    _, setter = use_value()
    with pytest.raises(PipeAlreadyDisposedError, match="pipe already disposed"):
        pipe.subscribe(setter)
