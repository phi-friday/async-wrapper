"""obtained from anyio.tests"""

from __future__ import annotations

import random
from itertools import chain
from typing import Any

import pytest
from anyio import CancelScope, create_task_group, fail_after, wait_all_tasks_blocked

from async_wrapper import Queue, create_queue
from async_wrapper.exception import (
    QueueBrokenError,
    QueueClosedError,
    QueueRestrictedError,
)
from async_wrapper.queue import _RestrictedQueue


def test_invalid_max_buffer() -> None:
    with pytest.raises(
        ValueError, match="max_buffer_size must be either an integer or math.inf"
    ):
        Queue(1.0)


def test_negative_max_buffer() -> None:
    with pytest.raises(ValueError, match="max_buffer_size cannot be negative"):
        Queue(-1)


@pytest.mark.anyio()
async def test_aget_then_aput() -> None:
    queue: Queue[str] = create_queue()
    result: list[str] = []

    async def getter() -> None:
        result.append(await queue.aget())
        result.append(await queue.aget())

    async with create_task_group() as task_group:
        task_group.start_soon(getter)
        await wait_all_tasks_blocked()
        await queue.aput("hello")
        await queue.aput("anyio")

    assert result == ["hello", "anyio"]


@pytest.mark.anyio()
async def test_aget_then_put() -> None:
    queue: Queue[str] = create_queue()
    result: list[str] = []

    async def getter() -> None:
        result.append(await queue.aget())

    async with create_task_group() as task_group:
        task_group.start_soon(getter)
        task_group.start_soon(getter)
        await wait_all_tasks_blocked()
        queue.put("hello")
        queue.put("anyio")

    assert sorted(result, reverse=True) == ["hello", "anyio"]


@pytest.mark.anyio()
async def test_aput_then_get() -> None:
    queue: Queue[str] = create_queue()
    async with create_task_group() as task_group:
        task_group.start_soon(queue.aput, "hello")
        await wait_all_tasks_blocked()
        assert queue.get() == "hello"


@pytest.mark.anyio()
async def test_aput_is_unblocked_after_get() -> None:
    queue: Queue[str] = create_queue()
    queue.put("hello")

    with fail_after(1):
        async with create_task_group() as task_group:
            task_group.start_soon(queue.aput, "anyio")
            await wait_all_tasks_blocked()
            assert queue.get() == "hello"

    assert queue.get() == "anyio"


@pytest.mark.anyio()
async def test_put_then_get() -> None:
    queue: Queue[str] = create_queue()
    queue.put("hello")
    queue.put("anyio")

    assert queue.get() == "hello"
    assert queue.get() == "anyio"


@pytest.mark.anyio()
async def test_iterate() -> None:
    queue: Queue[str] = create_queue()
    result: list[str] = []
    getter_queue = queue.clone.getter

    async def getter() -> None:
        async with getter_queue:
            async for item in getter_queue:
                result.append(item)  # noqa: PERF401

    async with create_task_group() as task_group:
        task_group.start_soon(getter)
        await queue.aput("hello")
        await queue.aput("anyio")
        await queue.aclose()

    assert result == ["hello", "anyio"]


@pytest.mark.anyio()
async def test_aget_aput_closed_queue() -> None:
    queue: Queue[Any] = create_queue()

    await queue.aclose()
    with pytest.raises(QueueBrokenError):
        queue.get()

    with pytest.raises(QueueBrokenError):
        await queue.aget()

    with pytest.raises(QueueBrokenError):
        queue.put(None)

    with pytest.raises(QueueBrokenError):
        await queue.aput(None)


@pytest.mark.anyio()
async def test_clone() -> None:
    queue: Queue[str] = create_queue(1)
    putter = queue.clone.putter
    getter = queue.clone.getter

    await queue.aclose()
    putter.put("hello")
    assert getter.get() == "hello"


@pytest.mark.anyio()
async def test_clone_closed() -> None:
    queue: Queue[str] = create_queue(1)
    await queue.aclose()

    with pytest.raises(QueueClosedError):
        _ = queue.clone.getter

    with pytest.raises(QueueClosedError):
        _ = queue.clone.putter


@pytest.mark.anyio()
async def test_clone_closed_using_cloning() -> None:
    queue: Queue[str] = create_queue(1)
    await queue.aclose()
    with pytest.raises(QueueClosedError, match="queue is already closed"):
        _ = queue.clone


@pytest.mark.anyio()
async def test_clone_closed_using_cloning_after_create() -> None:
    queue: Queue[str] = create_queue(1)
    clone = queue.clone
    await queue.aclose()
    with pytest.raises(QueueClosedError, match="queue is already closed"):
        _ = clone.getter


@pytest.mark.anyio()
async def test_aget_when_cancelled() -> None:
    queue: Queue[str] = create_queue()
    async with create_task_group() as task_group:
        task_group.start_soon(queue.aput, "hello")
        await wait_all_tasks_blocked()
        task_group.start_soon(queue.aput, "world")
        await wait_all_tasks_blocked()

        with CancelScope() as scope:
            scope.cancel()
            await queue.aget()

        assert await queue.aget() == "hello"
        assert await queue.aget() == "world"


@pytest.mark.anyio()
async def test_aput_when_cancelled() -> None:
    queue: Queue[str] = create_queue()
    result: list[str] = []

    async def getter() -> None:
        result.append(await queue.aget())

    async with create_task_group() as task_group:
        task_group.start_soon(getter)
        with CancelScope() as scope:
            scope.cancel()
            await queue.aput("hello")
        await queue.aput("world")

    assert result == ["world"]


@pytest.mark.anyio()
async def test_cancel_during_aget() -> None:
    receiver_scope: CancelScope | None = None
    queue: Queue[str] = create_queue()
    result: list[str] = []

    async def scoped_getter() -> None:
        nonlocal receiver_scope
        with CancelScope() as receiver_scope:
            result.append(await queue.aget())

        assert receiver_scope.cancel_called

    async with create_task_group() as tg:
        tg.start_soon(scoped_getter)
        await wait_all_tasks_blocked()
        queue.put("hello")
        assert receiver_scope is not None
        receiver_scope.cancel()

    assert result == ["hello"]


@pytest.mark.anyio()
async def test_close_queue_after_aput() -> None:
    queue: Queue[str] = create_queue()

    async def put() -> None:
        async with queue:
            await queue.aput("test")

    async def get() -> None:
        async with queue:
            assert await queue.aget() == "test"

    async with create_task_group() as task_group:
        task_group.start_soon(put)
        task_group.start_soon(get)


@pytest.mark.anyio()
async def test_statistics() -> None:
    queue: Queue[None] = create_queue(1)
    streams = queue._putter, queue._getter  # noqa: SLF001

    for stream in streams:
        statistics = stream.statistics()
        assert statistics.max_buffer_size == 1
        assert statistics.current_buffer_used == 0
        assert statistics.open_send_streams == 1
        assert statistics.open_receive_streams == 1
        assert statistics.tasks_waiting_send == 0
        assert statistics.tasks_waiting_receive == 0

    for stream in streams:
        async with create_task_group() as tg:
            # Test tasks_waiting_send
            queue.put(None)
            assert stream.statistics().current_buffer_used == 1
            tg.start_soon(queue.aput, None)
            await wait_all_tasks_blocked()
            assert stream.statistics().current_buffer_used == 1
            assert stream.statistics().tasks_waiting_send == 1
            queue.get()
            assert stream.statistics().current_buffer_used == 1
            assert stream.statistics().tasks_waiting_send == 0
            queue.get()
            assert stream.statistics().current_buffer_used == 0

            # Test tasks_waiting_receive
            tg.start_soon(queue.aget)
            await wait_all_tasks_blocked()
            assert stream.statistics().tasks_waiting_receive == 1
            queue.put(None)
            assert stream.statistics().tasks_waiting_receive == 0

        async with create_task_group() as tg:
            # Test tasks_waiting_send
            queue.put(None)
            assert stream.statistics().tasks_waiting_send == 0
            for _ in range(3):
                tg.start_soon(queue.aput, None)

            await wait_all_tasks_blocked()
            assert stream.statistics().tasks_waiting_send == 3
            for i in range(2, -1, -1):
                queue.get()
                assert stream.statistics().tasks_waiting_send == i

            queue.get()

        assert stream.statistics().current_buffer_used == 0
        assert stream.statistics().tasks_waiting_send == 0
        assert stream.statistics().tasks_waiting_receive == 0


@pytest.mark.anyio()
async def test_sync_close() -> None:
    queue: Queue[None] = create_queue(1)
    with queue:
        pass

    with pytest.raises(QueueBrokenError):
        queue.put(None)

    with pytest.raises(QueueBrokenError):
        queue.get()


@pytest.mark.anyio()
async def test_clone_each():
    queue: Queue[Any] = create_queue(1)

    async def test_put(q: Queue[Any]) -> None:
        async with q:
            await q.aput(1)

    async def test_get(q: Queue[Any]) -> None:
        async with q:
            await q.aget()

    async with create_task_group() as task_group:
        task_group.start_soon(test_put, queue.clone.putter)
        task_group.start_soon(test_put, queue.clone.putter)
        task_group.start_soon(test_get, queue.clone.getter)
        task_group.start_soon(test_get, queue.clone.getter)

    assert not queue._closed  # noqa: SLF001
    assert queue.empty()

    status = queue.statistics()
    assert status.open_receive_streams == 1
    assert status.open_send_streams == 1


@pytest.mark.anyio()
async def test_queue_async_iterator_aputter():
    queue: Queue[Any] = create_queue(10)

    async def put(value: Any, queue: Queue[Any]) -> None:
        async with queue:
            await queue.aput(value)

    async with create_task_group() as task_group:
        async with queue.aputter:
            for i in range(10):
                task_group.start_soon(put, i, queue.clone.putter)

    async with queue:
        result = [x async for x in queue]

    assert set(result) == set(range(10))


@pytest.mark.anyio()
async def test_queue_iterator_aputter():
    queue: Queue[Any] = create_queue(10)

    async def put(value: Any, queue: Queue[Any]) -> None:
        async with queue:
            await queue.aput(value)

    async with create_task_group() as task_group:
        async with queue.aputter:
            for i in range(10):
                task_group.start_soon(put, i, queue.clone.putter)

    async with queue:
        result = list(queue)

    assert set(result) == set(range(10))


@pytest.mark.anyio()
async def test_queue_async_iterator():
    queue: Queue[Any] = create_queue(10)

    async def put(value: Any, queue: Queue[Any]) -> None:
        async with queue:
            await queue.aput(value)

    async with create_task_group() as task_group:
        with queue.putter:
            for i in range(10):
                task_group.start_soon(put, i, queue.clone.putter)

    assert not queue._closed  # noqa: SLF001

    async with queue.agetter:
        result = [x async for x in queue]

    assert set(result) == set(range(10))
    assert queue._closed  # noqa: SLF001


@pytest.mark.anyio()
async def test_queue_iterator():
    queue: Queue[Any] = create_queue(10)

    async def put(value: Any, queue: Queue[Any]) -> None:
        async with queue:
            await queue.aput(value)

    async with create_task_group() as task_group:
        with queue.putter:
            for i in range(10):
                task_group.start_soon(put, i, queue.clone.putter)

    assert not queue._closed  # noqa: SLF001

    with queue.getter:
        result = list(queue)

    assert set(result) == set(range(10))
    assert queue._closed  # noqa: SLF001


@pytest.mark.anyio()
@pytest.mark.parametrize("x", range(1, 4))
async def test_queue_empty(x: int):
    queue: Queue[Any] = create_queue(x)

    assert queue.empty()
    await queue.aput(1)
    assert not queue.empty()
    await queue.aget()
    assert queue.empty()


@pytest.mark.anyio()
@pytest.mark.parametrize("x", range(1, 4))
async def test_queue_full(x: int):
    queue: Queue[Any] = create_queue(x)

    async with create_task_group() as task_group:
        for i in range(x):
            task_group.start_soon(queue.aput, i)

    assert queue.full()
    await queue.aget()
    assert not queue.full()
    await queue.aput(1)
    assert queue.full()


@pytest.mark.anyio()
@pytest.mark.parametrize("x", range(1, 4))
async def test_queue_size(x: int):
    queue: Queue[Any] = create_queue(x)

    async with create_task_group() as task_group:
        for i in range(x):
            task_group.start_soon(queue.aput, i)

    assert queue.qsize() == x
    await queue.aget()
    assert queue.qsize() == x - 1


@pytest.mark.anyio()
@pytest.mark.parametrize("x", range(1, 4))
async def test_queue_size_using_len(x: int):
    queue: Queue[Any] = create_queue(x)

    async with create_task_group() as task_group:
        for i in range(x):
            task_group.start_soon(queue.aput, i)

    assert len(queue) == x
    await queue.aget()
    assert len(queue) == x - 1


@pytest.mark.anyio()
@pytest.mark.parametrize("x", range(1, 4))
async def test_queue_length(x: int):
    queue: Queue[Any] = create_queue(x)
    assert queue.maxsize == x


@pytest.mark.anyio()
@pytest.mark.parametrize("x", chain((None,), range(1, 4)))
async def test_queue_repr(x: int | None):
    queue: Queue[Any] = create_queue(x)
    size = random.randint(1, x or 10)  # noqa: S311

    async with create_task_group() as task_group:
        for i in range(size):
            task_group.start_soon(queue.aput, i)

    expected_max = x or "inf"
    expected_repr = f"<Queue: max={expected_max}, size={size}>"
    assert repr(queue) == expected_repr


@pytest.mark.anyio()
@pytest.mark.parametrize("x", chain((None,), range(1, 4)))
async def test_cloning_repr(x: int | None):
    queue: Queue[Any] = create_queue(x)
    size = random.randint(1, x or 10)  # noqa: S311

    async with create_task_group() as task_group:
        for i in range(size):
            task_group.start_soon(queue.aput, i)

    expected_max = x or "inf"
    expected_repr = f"<Clone: max={expected_max}, size={size}>"
    assert repr(queue.clone) == expected_repr


@pytest.mark.anyio()
@pytest.mark.parametrize("x", chain((None,), range(1, 4)))
async def test_restricted_queue_repr(x: int | None):
    queue: Queue[Any] = create_queue(x)
    size = random.randint(1, x or 10)  # noqa: S311

    async with create_task_group() as task_group:
        for i in range(size):
            task_group.start_soon(queue.aput, i)

    expected_max = x or "inf"
    expected_repr = f"<RestrictedQueue: max={expected_max}, size={size}, where={{}}>"
    for where in ("getter", "putter"):
        clone = queue.clone.create(where)
        assert repr(clone) == expected_repr.format(where)


@pytest.mark.anyio()
async def test_restricted_queue_error():
    queue = create_queue()
    clone = queue.clone
    getter = clone.getter
    putter = clone.putter

    putter.put(1)
    with pytest.raises(QueueRestrictedError, match="putter is restricted"):
        getter.put(1)
    with pytest.raises(QueueRestrictedError, match="putter is restricted"):
        await getter.aput(1)
    with pytest.raises(QueueRestrictedError, match="getter is restricted"):
        putter.get()
    with pytest.raises(QueueRestrictedError, match="getter is restricted"):
        await putter.aget()

    with pytest.raises(TypeError, match="do not clone restricted queue"):
        _ = getter.clone
    with pytest.raises(TypeError, match="do not clone restricted queue"):
        _ = putter.clone


@pytest.mark.anyio()
async def test_restricted_queue_eixt():
    queue = create_queue()
    result: list[Any] = []

    async def aget(queue: Queue[Any]) -> None:
        with queue:
            value = await queue.aget()
        assert queue._closed  # noqa: SLF001
        result.append(value)

    def put(queue: Queue[Any]) -> None:
        with queue:
            queue.put(1)
        assert queue._closed  # noqa: SLF001

    async with create_task_group() as task_group:
        task_group.start_soon(aget, queue.clone.getter)
        put(queue.clone.putter)

    assert result == [1]


def test_create_restricted_queue_error():
    queue = create_queue()

    with pytest.raises(QueueRestrictedError, match="putter and getter are the same"):
        _ = _RestrictedQueue(queue, putter=True, getter=True)

    with pytest.raises(QueueRestrictedError, match="putter and getter are the same"):
        _ = _RestrictedQueue(queue, putter=False, getter=False)


def test_restricted_queue_stats():
    queue = create_queue()
    getter, putter = queue.clone.getter, queue.clone.putter

    assert getter.statistics() == queue.statistics()
    assert putter.statistics() == queue.statistics()
