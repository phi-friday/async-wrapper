from __future__ import annotations

from functools import partial
from typing import ClassVar, Literal

from async_wrapper import async_to_sync, sync_to_async, toggle_func
from async_wrapper.convert.asynclib.base import SyncToAsync
from async_wrapper.convert.synclib.base import AsyncToSync


class BaseTest:
    backend: ClassVar[Literal["loky", "thread"]]

    @property
    def epsilon(self) -> float:
        if self.backend == "loky":
            return 0.5
        if self.backend == "thread":
            return 0.1

        raise NotImplementedError

    @classmethod
    def sync_to_async(cls) -> SyncToAsync:
        return sync_to_async(cls.backend)

    @classmethod
    def async_to_sync(cls) -> AsyncToSync:
        return async_to_sync(cls.backend)

    @classmethod
    def toggle(cls):  # noqa: ANN206
        return partial(toggle_func, backend=cls.backend)
