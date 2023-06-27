from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from async_wrapper.convert.synclib.base import AsyncToSync

__all__ = ["get_sync_convertor"]

DEFAULT_BACKEND = "thread"
SyncBackendType = Literal["thread", "loky"]


def get_sync_convertor(
    backend: SyncBackendType | None = None,
) -> AsyncToSync:
    """get sync convertor

    Args:
        backend: thread or loky. Defaults to None.

    Returns:
        async to sync
    """
    if not backend:
        backend = DEFAULT_BACKEND

    module = importlib.import_module(f"._{backend}", __package__)
    return module.async_to_sync
