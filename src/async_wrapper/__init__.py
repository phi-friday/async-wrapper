from __future__ import annotations

from typing import Any

from async_wrapper.convert import async_to_sync, sync_to_async, toggle_func
from async_wrapper.pipe import Pipe, SimpleDisposable, create_disposable
from async_wrapper.queue import Queue, create_queue
from async_wrapper.task_group import TaskGroupWrapper, create_task_group_wrapper
from async_wrapper.wait import Completed, Waiter, wait_for

__all__ = [
    "Completed",
    "Pipe",
    "Queue",
    "SimpleDisposable",
    "TaskGroupWrapper",
    "Waiter",
    "async_to_sync",
    "create_disposable",
    "create_queue",
    "create_task_group_wrapper",
    "sync_to_async",
    "toggle_func",
    "wait_for",
]

__version__: str


def __getattr__(name: str) -> Any:  # pragma: no cover
    from importlib.metadata import version  # noqa: PLC0415

    if name == "__version__":
        _version = version("async_wrapper")
        globals()["__version__"] = _version
        return _version

    error_msg = f"The attribute named {name!r} is undefined."
    raise AttributeError(error_msg)
