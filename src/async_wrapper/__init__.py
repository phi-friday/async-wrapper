from __future__ import annotations

from typing import Any

from .convert import async_to_sync, sync_to_async, toggle_func
from .pipe import Pipe
from .queue import Queue, create_queue
from .task_group import TaskGroupWrapper, create_task_group_wrapper
from .wait import Completed, Waiter, wait_for

__all__ = [
    "TaskGroupWrapper",
    "Queue",
    "Waiter",
    "Completed",
    "Pipe",
    "toggle_func",
    "async_to_sync",
    "sync_to_async",
    "create_task_group_wrapper",
    "create_queue",
    "wait_for",
]

__version__: str


def __getattr__(name: str) -> Any:  # pragma: no cover
    from importlib.metadata import version

    if name == "__version__":
        return version("async_wrapper")

    error_msg = f"The attribute named {name!r} is undefined."
    raise AttributeError(error_msg)
