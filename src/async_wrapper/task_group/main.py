from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from async_wrapper.task_group import _anyio as anyio_taskgroup

__all__ = ["get_taskgroup_wrapper"]

DEFAULT_BACKEND = "anyio"
TaskGroupBackendType = Literal["anyio"]


def get_taskgroup_wrapper(
    backend: TaskGroupBackendType | str | None = None,
) -> type[anyio_taskgroup.SoonWrapper]:
    """get taskgroup wrapper

    Args:
        backend: anyio. Defaults to None.

    Returns:
        taskgroup soon wrapper
    """
    if not backend:
        backend = DEFAULT_BACKEND

    module = importlib.import_module(f"._{backend}", __package__)
    return module.wrap_soon
