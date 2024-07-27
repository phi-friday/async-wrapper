from __future__ import annotations

from typing import Any

from async_wrapper.convert import async_to_sync, sync_to_async, toggle_func
from async_wrapper.pipe import Pipe, SimpleDisposable, create_disposable
from async_wrapper.queue import Queue, create_queue
from async_wrapper.task_group import TaskGroupWrapper, create_task_group_wrapper
from async_wrapper.wait import Completed, Waiter, wait_for

__all__ = [
    "TaskGroupWrapper",
    "Queue",
    "Waiter",
    "Completed",
    "Pipe",
    "SimpleDisposable",
    "toggle_func",
    "async_to_sync",
    "sync_to_async",
    "create_task_group_wrapper",
    "create_queue",
    "wait_for",
    "create_disposable",
]

__version__: str


def __getattr__(name: str) -> Any:  # pragma: no cover
    from importlib.metadata import version

    if name == "__version__":
        return version("async_wrapper")

    error_msg = f"The attribute named {name!r} is undefined."
    raise AttributeError(error_msg)
