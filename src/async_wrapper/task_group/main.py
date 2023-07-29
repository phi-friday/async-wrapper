from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Literal, overload

if TYPE_CHECKING:
    from async_wrapper.task_group import _anyio as anyio_task_group
    from async_wrapper.task_group import _asyncio as asyncio_task_group
    from async_wrapper.task_group.base import TaskGroupFactory

__all__ = ["get_task_group_wrapper", "get_task_group_factory", "get_semaphore_class"]

DEFAULT_BACKEND = "anyio"
TaskGroupBackendType = Literal["asyncio", "anyio"]


@overload
def get_task_group_wrapper(
    backend: Literal["anyio"] | None = ...,
) -> type[anyio_task_group.SoonWrapper]:
    ...


@overload
def get_task_group_wrapper(
    backend: Literal["asyncio"] = ...,
) -> type[asyncio_task_group.SoonWrapper]:
    ...


def get_task_group_wrapper(
    backend: TaskGroupBackendType | None = None,
) -> type[anyio_task_group.SoonWrapper] | type[asyncio_task_group.SoonWrapper]:
    """get task group wrapper

    Args:
        backend: anyio or asyncio. Defaults to None.

    Returns:
        task group soon wrapper
    """
    if not backend:
        backend = DEFAULT_BACKEND

    module = importlib.import_module(f"._{backend}", __package__)
    return module.wrap_soon


@overload
def get_task_group_factory(
    backend: Literal["anyio"] | None = ...,
) -> TaskGroupFactory[anyio_task_group.TaskGroup]:
    ...


@overload
def get_task_group_factory(
    backend: Literal["asyncio"] = ...,
) -> TaskGroupFactory[asyncio_task_group.TaskGroup]:
    ...


def get_task_group_factory(
    backend: TaskGroupBackendType | None = None,
) -> (
    TaskGroupFactory[asyncio_task_group.TaskGroup]
    | TaskGroupFactory[anyio_task_group.TaskGroup]
):
    """get task group factory func

    Args:
        backend: asyncio or anyio. Defaults to None.

    Returns:
        task group factory
    """
    if not backend:
        backend = DEFAULT_BACKEND

    module = importlib.import_module(f"._{backend}", __package__)
    return module.get_task_group


@overload
def get_semaphore_class(
    backend: Literal["anyio"] | None = ...,
) -> type[anyio_task_group.AnyioSemaphore]:
    ...


@overload
def get_semaphore_class(
    backend: Literal["asyncio"] = ...,
) -> type[asyncio_task_group.AsyncioSemaphore]:
    ...


def get_semaphore_class(
    backend: TaskGroupBackendType | None = None,
) -> type[asyncio_task_group.AsyncioSemaphore] | type[anyio_task_group.AnyioSemaphore]:
    """get semaphore class using in wrap func

    Args:
        backend: asyncio or anyio. Defaults to None.

    Returns:
        semaphore class
    """
    if not backend:
        backend = DEFAULT_BACKEND

    module = importlib.import_module(f"._{backend}", __package__)
    return module.get_semaphore_class()
