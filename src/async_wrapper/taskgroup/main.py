from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Literal, overload

if TYPE_CHECKING:
    from async_wrapper.taskgroup import _anyio as anyio_taskgroup
    from async_wrapper.taskgroup import _asyncio as asyncio_taskgroup
    from async_wrapper.taskgroup.base import TaskGroupFactory

__all__ = ["get_taskgroup_wrapper", "get_taskgroup_factory"]

DEFAULT_BACKEND = "asyncio"
TaskGroupBackendType = Literal["asyncio", "anyio"]


@overload
def get_taskgroup_wrapper(
    backend: Literal["asyncio"] | None = ...,
) -> type[asyncio_taskgroup.SoonWrapper]:
    ...


@overload
def get_taskgroup_wrapper(
    backend: Literal["anyio"] = ...,
) -> type[anyio_taskgroup.SoonWrapper]:
    ...


def get_taskgroup_wrapper(
    backend: TaskGroupBackendType | None = None,
) -> type[anyio_taskgroup.SoonWrapper] | type[asyncio_taskgroup.SoonWrapper]:
    """get taskgroup wrapper

    Args:
        backend: anyio or asyncio. Defaults to None.

    Returns:
        taskgroup soon wrapper
    """
    if not backend:
        backend = DEFAULT_BACKEND

    module = importlib.import_module(f"._{backend}", __package__)
    return module.wrap_soon


@overload
def get_taskgroup_factory(
    backend: Literal["asyncio"] | None = ...,
) -> TaskGroupFactory[asyncio_taskgroup.TaskGroup]:
    ...


@overload
def get_taskgroup_factory(
    backend: Literal["anyio"] = ...,
) -> TaskGroupFactory[anyio_taskgroup.TaskGroup]:
    ...


def get_taskgroup_factory(
    backend: TaskGroupBackendType | None = None,
) -> (
    TaskGroupFactory[asyncio_taskgroup.TaskGroup]
    | TaskGroupFactory[anyio_taskgroup.TaskGroup]
):
    """get taskgroup factory func

    Args:
        backend: asyncio or anyio. Defaults to None.

    Returns:
        task group factory
    """
    if not backend:
        backend = DEFAULT_BACKEND

    module = importlib.import_module(f"._{backend}", __package__)
    return module.get_taskgroup
