from __future__ import annotations

from collections import deque
from threading import local
from typing import TYPE_CHECKING, Any, Callable, Generic, TypeVar

from typing_extensions import ParamSpec

from .exception import PendingError

if TYPE_CHECKING:
    from async_wrapper.task_group.future import Future

ValueT_co = TypeVar("ValueT_co", covariant=True)
OtherValueT_co = TypeVar("OtherValueT_co", covariant=True)
ParamT = ParamSpec("ParamT")
OtherParamT = ParamSpec("OtherParamT")
Pending = local()

__all__ = ["SoonValue"]


class SoonValue(Generic[ValueT_co]):
    def __init__(
        self,
        future: Future[ValueT_co] | None = None,
    ) -> None:
        self._value = Pending
        if future is None:
            self._future = None
        else:
            self._set_future(future)
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

    @property
    def future(self) -> Future[ValueT_co]:
        """value future"""
        if self._future is None:
            raise AttributeError("future is None")
        return self._future

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

    def _set_future(
        self,
        future: Future[ValueT_co],
    ) -> None:
        if self._value is not Pending:
            raise AttributeError("value is already setted")
        future.add_done_callback(self._set_from_future)
        self._future = future

    def _set_from_future(
        self,
        future: Future[ValueT_co],
    ) -> None:
        if future.exception() is None:
            self._value = future.result()
        self._run_callbacks()
        if self._future is not None:
            self._future = None
