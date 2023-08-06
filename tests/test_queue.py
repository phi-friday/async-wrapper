"""obtained from anyio.tests"""
from __future__ import annotations

from typing import Any

import pytest
from anyio import CancelScope, create_task_group, fail_after, wait_all_tasks_blocked

from async_wrapper import Queue
from async_wrapper.exception import QueueBrokenError


def test_invalid_max_buffer() -> None:
    with pytest.raises(
        ValueError,
        match="max_buffer_size must be either an integer or math.inf",
    ):
        Queue(1.0)


def test_negative_max_buffer() -> None:
    with pytest.raises(ValueError, match="max_buffer_size cannot be negative"):
        Queue(-1)


@pytest.mark.anyio()
async def test_aget_then_aput() -> None:
    queue: Queue[str] = Queue()
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
    queue: Queue[str] = Queue()
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
    queue: Queue[str] = Queue()
    async with create_task_group() as task_group:
        task_group.start_soon(queue.aput, "hello")
        await wait_all_tasks_blocked()
        assert queue.get() == "hello"


@pytest.mark.anyio()
async def test_aput_is_unblocked_after_get() -> None:
    queue: Queue[str] = Queue()
    queue.put("hello")

    with fail_after(1):
        async with create_task_group() as task_group:
            task_group.start_soon(queue.aput, "anyio")
            await wait_all_tasks_blocked()
            assert queue.get() == "hello"

    assert queue.get() == "anyio"


@pytest.mark.anyio()
async def test_put_then_get() -> None:
    queue: Queue[str] = Queue()
    queue.put("hello")
    queue.put("anyio")

    assert queue.get() == "hello"
    assert queue.get() == "anyio"


@pytest.mark.anyio()
async def test_iterate() -> None:
    queue: Queue[str] = Queue()
    result: list[str] = []
    clone = queue.clone(getter=True)

    async def getter() -> None:
        async with clone:
            async for item in clone:
                result.append(item)  # noqa: PERF402

    async with create_task_group() as task_group:
        task_group.start_soon(getter)
        await queue.aput("hello")
        await queue.aput("anyio")
        await queue.aclose()

    assert result == ["hello", "anyio"]


@pytest.mark.anyio()
async def test_aget_aput_closed_queue() -> None:
    queue: Queue[Any] = Queue()

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
    queue: Queue[str] = Queue(1)
    queue2 = queue.clone(putter=True, getter=True)

    await queue.aclose()
    queue2.put("hello")
    assert queue2.get() == "hello"


@pytest.mark.anyio()
async def test_clone_closed() -> None:
    queue: Queue[str] = Queue(1)
    await queue.aclose()
    pytest.raises(QueueBrokenError, queue.clone)


@pytest.mark.anyio()
async def test_aget_when_cancelled() -> None:
    queue: Queue[str] = Queue()
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
    queue: Queue[str] = Queue()
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
    queue: Queue[str] = Queue()
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
    queue: Queue[str] = Queue()

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
    queue: Queue[None] = Queue(1)
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
    queue: Queue[None] = Queue(1)
    with queue:
        pass

    with pytest.raises(QueueBrokenError):
        queue.put(None)

    with pytest.raises(QueueBrokenError):
        queue.get()


@pytest.mark.anyio()
async def test_clone_each():
    queue: Queue[Any] = Queue(1)

    async def test_put(q: Queue[Any]) -> None:
        async with q:
            await q.aput(1)

    async def test_get(q: Queue[Any]) -> None:
        async with q:
            await q.aget()

    async with create_task_group() as task_group:
        task_group.start_soon(test_put, queue.clone(putter=True))
        task_group.start_soon(test_put, queue.clone(putter=True))
        task_group.start_soon(test_get, queue.clone(getter=True))
        task_group.start_soon(test_get, queue.clone(getter=True))

    assert not queue._closed  # noqa: SLF001
    assert queue.empty()

    status = queue.statistics()
    assert status.open_receive_streams == 1
    assert status.open_send_streams == 1


@pytest.mark.anyio()
def test_queue_clone_uset():
    queue: Queue[Any] = Queue(1)
    with pytest.raises(ValueError, match="putter and getter are None."):
        queue.clone()


@pytest.mark.anyio()
async def test_queue_async_iterator_aputter():
    queue: Queue[Any] = Queue(10)

    async def put(value: Any, queue: Queue[Any]) -> None:
        async with queue:
            await queue.aput(value)

    async with create_task_group() as task_group:
        async with queue.aputter:
            for i in range(10):
                task_group.start_soon(put, i, queue.clone(putter=True))

    async with queue:
        result = [x async for x in queue]

    assert set(result) == set(range(10))


@pytest.mark.anyio()
async def test_queue_iterator_aputter():
    queue: Queue[Any] = Queue(10)

    async def put(value: Any, queue: Queue[Any]) -> None:
        async with queue:
            await queue.aput(value)

    async with create_task_group() as task_group:
        async with queue.aputter:
            for i in range(10):
                task_group.start_soon(put, i, queue.clone(putter=True))

    async with queue:
        result = list(queue)

    assert set(result) == set(range(10))


@pytest.mark.anyio()
async def test_queue_async_iterator_putter():
    queue: Queue[Any] = Queue(10)

    async def put(value: Any, queue: Queue[Any]) -> None:
        async with queue:
            await queue.aput(value)

    async with create_task_group() as task_group:
        with queue.putter:
            for i in range(10):
                task_group.start_soon(put, i, queue.clone(putter=True))

    async with queue:
        result = [x async for x in queue]

    assert set(result) == set(range(10))


@pytest.mark.anyio()
async def test_queue_iterator_putter():
    queue: Queue[Any] = Queue(10)

    async def put(value: Any, queue: Queue[Any]) -> None:
        async with queue:
            await queue.aput(value)

    async with create_task_group() as task_group:
        with queue.putter:
            for i in range(10):
                task_group.start_soon(put, i, queue.clone(putter=True))

    async with queue:
        result = list(queue)

    assert set(result) == set(range(10))
