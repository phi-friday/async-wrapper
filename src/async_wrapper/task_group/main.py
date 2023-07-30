from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from async_wrapper.task_group import _anyio as anyio_task_group
    from async_wrapper.task_group.base import TaskGroupFactory

__all__ = ["get_task_group_wrapper", "get_task_group_factory", "get_semaphore_class"]

DEFAULT_BACKEND = "anyio"
TaskGroupBackendType = Literal["anyio", "asyncio", "trio"]
ValidTaskGroupBackendType = Literal["anyio"]


def get_task_group_wrapper(
    backend: TaskGroupBackendType | None = None,
) -> type[anyio_task_group.SoonWrapper]:
    """get task group wrapper

    Args:
        backend: anyio. Defaults to None.

    Returns:
        task group soon wrapper
    """
    backend = _get_valid_backend(backend)
    module = importlib.import_module(f"._{backend}", __package__)
    return module.wrap_soon


def get_task_group_factory(
    backend: TaskGroupBackendType | None = None,
) -> TaskGroupFactory[anyio_task_group.TaskGroup]:
    """get task group factory func

    Args:
        backend: anyio. Defaults to None.

    Returns:
        task group factory
    """
    backend = _get_valid_backend(backend)
    module = importlib.import_module(f"._{backend}", __package__)
    return module.get_task_group


def get_semaphore_class(
    backend: TaskGroupBackendType | None = None,
) -> type[anyio_task_group.AnyioSemaphore]:
    """get semaphore class using in wrap func

    Args:
        backend: anyio. Defaults to None.

    Returns:
        semaphore class
    """
    backend = _get_valid_backend(backend)
    module = importlib.import_module(f"._{backend}", __package__)
    return module.get_semaphore_class()


def _get_valid_backend(backend: str | None) -> ValidTaskGroupBackendType:
    if not backend:
        return DEFAULT_BACKEND
    if backend in {"anyio", "asyncio", "trio"}:
        return "anyio"
    raise NotImplementedError
