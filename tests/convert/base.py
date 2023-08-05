from __future__ import annotations

from typing import Final

from async_wrapper import async_to_sync, sync_to_async, toggle_func
from async_wrapper.convert.abc import AsyncToSync, SyncToAsync, Toggle


class BaseTest:
    epsilon: Final[float] = 0.1

    @classmethod
    def sync_to_async(cls) -> SyncToAsync:
        return sync_to_async

    @classmethod
    def async_to_sync(cls) -> AsyncToSync:
        return async_to_sync

    @classmethod
    def toggle(cls) -> Toggle:
        return toggle_func
