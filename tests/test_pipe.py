from __future__ import annotations

import inspect
from collections import deque
from contextlib import suppress
from functools import partial
from typing import Any, Awaitable, Callable

import anyio
import pytest
from typing_extensions import TypeVar, override

from .base import Timer
from async_wrapper.exception import AlreadyDisposedError
from async_wrapper.pipe import (
    Disposable,
    DisposableWithCallback,
    Pipe,
    SimpleDisposable,
    Subscribable,
    create_disposable,
)

pytestmark = pytest.mark.anyio

ValueT = TypeVar("ValueT", infer_variance=True)
SubscribableT = TypeVar("SubscribableT", bound=Subscribable[Any, Any])

EPSILON: float = 0.1


class CustomDisposable:
    def __init__(self, dispose: Callable[[], Any] | None = None) -> None:
        self.value = None
        self.disposed = False
        self._dispose = dispose

    @property
    def is_disposed(self) -> bool:
        return self.disposed

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


class CustomDisposableWithCallback(CustomDisposable):
    def __init__(self, dispose: Callable[[], Any] | None = None) -> None:
        super().__init__(dispose)
        self._subscribables: deque[Subscribable[Any, Any]] = deque()

    @override
    async def dispose(self) -> Any:
        await super().dispose()
        for subscribable in self._subscribables:
            subscribable.unsubscribe(self)

    def prepare_callback(self, subscribable: Subscribable[Any, Any]) -> Any:
        self._subscribables.append(subscribable)


class CustomSubscribable(CustomDisposable):
    def __init__(self, dispose: Callable[[], Any] | None = None) -> None:
        super().__init__(dispose)
        self._listeners: dict[Disposable[Any, Any], bool] = {}

    @property
    def size(self) -> int:
        return len(self._listeners)

    @override
    async def next(self, value: Any) -> Any:
        result = await super().next(value)
        for listener in self._listeners:
            await listener.next(result)

    @override
    async def dispose(self) -> Any:
        with suppress(TypeError):
            await super().dispose()
        for listener, do_dispose in self._listeners.items():
            if not do_dispose:
                continue
            await listener.dispose()

    def subscribe(
        self,
        disposable: Disposable[Any, Any] | Callable[[Any], Awaitable[Any]],
        *,
        dispose: bool = True,
    ) -> Any:
        if not isinstance(disposable, Disposable):
            disposable = create_disposable(disposable)
        self._listeners[disposable] = dispose
        if isinstance(disposable, DisposableWithCallback):
            disposable.prepare_callback(self)

    def unsubscribe(self, disposable: Disposable[Any, Any]) -> None:
        self._listeners.pop(disposable, None)


@pytest.fixture(
    params=[
        pytest.param(CustomSubscribable, id="custom-subscribable"),
        pytest.param(Pipe, id="pipe"),
    ]
)
def subscribable_type(request: pytest.FixtureRequest) -> type[Subscribable[Any, Any]]:
    return request.param


async def as_tuple(value: ValueT) -> tuple[ValueT]:
    await anyio.sleep(0)
    return (value,)


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


def test_custom_disposable():
    disposable = CustomDisposable()
    assert isinstance(disposable, Disposable)


def test_custom_disposable_with_callback():
    disposable = CustomDisposableWithCallback()
    assert isinstance(disposable, DisposableWithCallback)


def test_custom_subscribable():
    disposable = CustomSubscribable()
    assert isinstance(disposable, Subscribable)


@pytest.mark.parametrize("x", range(1, 4))
async def test_subscribe(x: int, subscribable_type: type[Subscribable[Any, Any]]):
    pipe: Subscribable[int, Any] = _construct_subcribable(subscribable_type, as_tuple)
    getter, setter = use_value()
    pipe.subscribe(setter)

    await pipe.next(x)
    result = await getter()
    assert result is not None


@pytest.mark.parametrize("x", range(1, 4))
async def test_subscribe_interface(
    x: int, subscribable_type: type[Subscribable[Any, Any]]
):
    pipe: Subscribable[int, int] = _construct_subcribable(
        subscribable_type, return_self
    )
    disposable = CustomDisposable()
    pipe.subscribe(disposable)

    assert disposable.value is None
    await pipe.next(x)

    assert isinstance(disposable.value, int)
    assert disposable.value == x


@pytest.mark.parametrize("x", range(1, 4))
async def test_subscribe_many(x: int, subscribable_type: type[Subscribable[Any, Any]]):
    size = 10
    check: list[Any] = [False] * size

    async def hit(value: Any, index: int) -> None:
        nonlocal check
        await anyio.sleep(0)
        check[index] = value

    pipe: Subscribable[int, tuple[Any, ...]] = _construct_subcribable(
        subscribable_type, as_tuple
    )
    for index in range(size):
        pipe.subscribe(partial(hit, index=index))

    await pipe.next(x)
    if subscribable_type is CustomSubscribable:
        assert check == [x] * size
    else:
        assert check == [(x,)] * size


@pytest.mark.parametrize("x", range(1, 4))
async def test_subscribe_chain(x: int, subscribable_type: type[Subscribable[Any, Any]]):
    pipe1: Subscribable[int, int] = _construct_subcribable(
        subscribable_type, return_self
    )
    pipe2: Subscribable[int, tuple[int]] = _construct_subcribable(
        subscribable_type, as_tuple
    )
    pipe3: Subscribable[Any, tuple[Any, ...]] = _construct_subcribable(
        subscribable_type, as_tuple
    )

    getter, setter = use_value()
    pipe1.subscribe(pipe2)
    pipe2.subscribe(pipe3)
    pipe3.subscribe(setter)

    await pipe1.next(x)
    result = await getter()

    if subscribable_type is CustomSubscribable:
        assert isinstance(result, int)
        assert result == x
    else:
        assert isinstance(result, tuple)
        assert result == ((x,),)


async def test_unsubscribe(subscribable_type: type[Subscribable[Any, Any]]):
    pipe: Subscribable[Any, Any] = _construct_subcribable(
        subscribable_type, return_self
    )
    getter, setter = use_value()
    disposable = create_disposable(setter)
    pipe.subscribe(disposable)

    await pipe.next(0)
    result = await getter()
    assert result == 0

    pipe.unsubscribe(disposable)
    await pipe.next(1)
    result = await getter()
    assert result != 1


async def test_prepare_callback(subscribable_type: type[Subscribable[Any, Any]]):
    pipe: Subscribable[Any, Any] = _construct_subcribable(
        subscribable_type, return_self
    )
    disposable = CustomDisposableWithCallback()

    pipe.subscribe(disposable)
    assert pipe.size == 1
    await disposable.dispose()
    assert pipe.size == 0


async def test_empty_dispose(subscribable_type: type[Subscribable[Any, Any]]):
    pipe: Subscribable[Any, Any] = _construct_subcribable(
        subscribable_type, return_self
    )
    disposable = CustomDisposable()
    pipe.subscribe(disposable)

    assert disposable.disposed is False
    await pipe.dispose()
    assert disposable.disposed is True


async def test_dispose(subscribable_type: type[Subscribable[Any, Any]]):
    flag: bool = False

    async def hit() -> None:
        nonlocal flag
        await anyio.sleep(0)
        flag = True

    pipe: Subscribable[Any, Any]
    if subscribable_type is Pipe:
        pipe = _construct_subcribable(subscribable_type, return_self, dispose=hit)
    else:
        pipe = _construct_subcribable(subscribable_type, dispose=hit)

    disposable = CustomDisposable()
    pipe.subscribe(disposable)

    assert disposable.disposed is False
    assert flag is False
    await pipe.dispose()
    assert disposable.disposed is True
    assert flag is True


async def test_dispose_many(subscribable_type: type[Subscribable[Any, Any]]):
    size = 10
    check: list[Any] = [False] * size

    async def hit(index: int) -> None:
        nonlocal check
        await anyio.sleep(0)
        check[index] = True

    pipe: Subscribable[Any, Any] = _construct_subcribable(
        subscribable_type, return_self
    )
    for index in range(size):
        disposable = CustomDisposable(dispose=partial(hit, index=index))
        pipe.subscribe(disposable)

    assert all(x is False for x in check)
    await pipe.dispose()
    assert all(x is True for x in check)


async def test_dispose_chain(subscribable_type: type[Subscribable[Any, Any]]):
    pipe: Subscribable[Any, Any] = _construct_subcribable(
        subscribable_type, return_self
    )
    disposable1 = _construct_subcribable(subscribable_type, return_self)
    disposable2 = CustomDisposable()

    pipe.subscribe(disposable1)
    disposable1.subscribe(disposable2)

    if isinstance(disposable1, Pipe):
        assert disposable1.is_disposed is False
    assert disposable2.disposed is False
    await pipe.dispose()

    if isinstance(disposable1, Pipe):
        assert disposable1.is_disposed is True
    assert disposable2.disposed is True


async def test_pipe_dispose_only_once():
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


async def test_do_not_dispose(subscribable_type: type[Subscribable[Any, Any]]):
    flag: bool = False

    async def hit() -> None:
        nonlocal flag
        await anyio.sleep(0)
        flag = True

    pipe: Subscribable[int, int] = _construct_subcribable(
        subscribable_type, return_self
    )
    disposable = CustomDisposable(dispose=hit)
    pipe.subscribe(disposable, dispose=False)

    assert disposable.disposed is False
    await pipe.dispose()
    assert disposable.disposed is False


async def test_pipe_semaphore():
    size = 3
    check: list[Any] = [False] * size

    async def hit(value: Any, index: int) -> None:
        nonlocal check
        await anyio.sleep(EPSILON)
        check[index] = value

    sema_value = 2
    sema = anyio.Semaphore(sema_value)
    pipe: Pipe[int, tuple[Any, ...]] = Pipe(as_tuple, context={"semaphore": sema})
    for index in range(size):
        pipe.subscribe(partial(hit, index=index))

    with Timer() as timer:
        await pipe.next(1)

    q = size // sema_value + 1
    assert timer.term < EPSILON * q + EPSILON


async def test_pipe_limit():
    size = 3
    check: list[Any] = [False] * size

    async def hit(value: Any, index: int) -> None:
        nonlocal check
        await anyio.sleep(EPSILON)
        check[index] = value

    limit_value = 2
    limit = anyio.CapacityLimiter(limit_value)
    pipe: Pipe[int, tuple[Any, ...]] = Pipe(as_tuple, context={"limiter": limit})
    for index in range(size):
        pipe.subscribe(partial(hit, index=index))

    with Timer() as timer:
        await pipe.next(1)

    q = size // limit_value + 1
    assert timer.term < EPSILON * q + EPSILON


async def test_pipe_lock():
    size = 3
    check: list[Any] = [False] * size

    async def hit(value: Any, index: int) -> None:
        nonlocal check
        await anyio.sleep(EPSILON)
        check[index] = value

    lock = anyio.Lock()
    pipe: Pipe[int, tuple[Any, ...]] = Pipe(as_tuple, context={"lock": lock})
    for index in range(size):
        pipe.subscribe(partial(hit, index=index))

    with Timer() as timer:
        await pipe.next(1)

    assert timer.term < EPSILON * size + EPSILON


async def test_pipe_next_after_disposed():
    flag: bool = False

    async def hit(value: Any) -> None:  # noqa: ARG001
        nonlocal flag
        await anyio.sleep(0)
        flag = True

    pipe = Pipe(hit)
    await pipe.dispose()
    assert pipe.is_disposed is True

    with pytest.raises(AlreadyDisposedError, match="pipe already disposed"):
        await pipe.next(1)


async def test_pipe_subscribe_after_disposed():
    pipe = Pipe(return_self)
    await pipe.dispose()
    _, setter = use_value()
    with pytest.raises(AlreadyDisposedError, match="pipe already disposed"):
        pipe.subscribe(setter)


async def test_simple_disposable():
    disposable = SimpleDisposable(return_self)
    assert isinstance(disposable, Disposable)


async def test_construct_disposable():
    disposable = create_disposable(return_self)
    assert isinstance(disposable, Disposable)


async def test_simple_dispose():
    disposable = create_disposable(return_self)
    assert disposable.is_disposed is False
    await disposable.dispose()
    assert disposable.is_disposed is True


async def test_simple_prepare_callback():
    disposable: SimpleDisposable[Any, Any] = create_disposable(return_self)
    subscribable: Subscribable[Any, Any] = CustomSubscribable()
    assert not disposable._journals  # noqa: SLF001
    disposable.prepare_callback(subscribable)
    assert disposable._journals  # noqa: SLF001
    assert len(disposable._journals) == 1  # noqa: SLF001


async def test_simple_next_after_disposed():
    disposable: SimpleDisposable[Any, Any] = create_disposable(return_self)
    await disposable.dispose()
    with pytest.raises(AlreadyDisposedError, match="disposable already disposed"):
        await disposable.next(1)


async def test_simple_prepare_callback_after_disposed():
    disposable: SimpleDisposable[Any, Any] = create_disposable(return_self)
    subscribable: Subscribable[Any, Any] = CustomSubscribable()
    await disposable.dispose()
    with pytest.raises(AlreadyDisposedError, match="disposable already disposed"):
        disposable.prepare_callback(subscribable)


def _construct_subcribable(
    subscribable_type: type[SubscribableT], *args: Any, **kwargs: Any
) -> SubscribableT:
    return subscribable_type(*args, **kwargs)
