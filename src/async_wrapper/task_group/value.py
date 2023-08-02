from __future__ import annotations

from collections import deque
from threading import local
from typing import Any, Callable, Generic, TypeVar

from .exception import PendingError

ValueT_co = TypeVar("ValueT_co", covariant=True)
Pending = local()

__all__ = ["SoonValue"]


class SoonValue(Generic[ValueT_co]):
    def __init__(self) -> None:
        self._value: ValueT_co | local = Pending
        self.done_callbacks: deque[Callable[[SoonValue[ValueT_co]], Any]] = deque()

    def __repr__(self) -> str:
        status = "pending" if self._value is Pending else "done"
        return f"<SoonValue: status={status}>"

    @property
    def value(self) -> ValueT_co:
        """soon value"""
        if self._value is Pending:
            raise PendingError
        return self._value  # type: ignore

    @property
    def is_ready(self) -> bool:
        """value status"""
        return self._value is not Pending

    def add_done_callback(
        self,
        callback: Callable[[SoonValue[ValueT_co]], Any],
    ) -> None:
        """add value callback.

        run after set value.

        Args:
            callback: value callback.
        """
        self.done_callbacks.append(callback)

    def _run_callbacks(self) -> None:
        for callback in self.done_callbacks:
            callback(self)
        self.done_callbacks.clear()
