from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from async_wrapper.convert.asynclib.base import SyncToAsync

__all__ = ["get_async_convertor"]

DEFAULT_BACKEND = "thread"
AsyncBackendType = Literal["thread", "loky"]


def get_async_convertor(
    backend: AsyncBackendType | None = None,
) -> SyncToAsync:
    """get async convertor

    Args:
        backend: thread. Defaults to None.

    Returns:
        sync to async
    """
    if not backend:
        backend = DEFAULT_BACKEND

    module = importlib.import_module(f"._{backend}", __package__)
    return module.sync_to_async
