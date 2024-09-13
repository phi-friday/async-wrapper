from __future__ import annotations

from typing import Final

from async_wrapper import async_to_sync, sync_to_async, toggle_func


class BaseTest:
    epsilon: Final[float] = 0.1

    @classmethod
    def sync_to_async(cls):  # noqa: ANN206
        return sync_to_async

    @classmethod
    def async_to_sync(cls):  # noqa: ANN206
        return async_to_sync

    @classmethod
    def toggle(cls):  # noqa: ANN206
        return toggle_func
