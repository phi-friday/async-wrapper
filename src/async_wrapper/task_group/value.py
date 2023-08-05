from __future__ import annotations

from threading import local
from typing import Generic, TypeVar

from async_wrapper.exception import PendingError

ValueT_co = TypeVar("ValueT_co", covariant=True)
Pending = local()

__all__ = ["SoonValue"]


class SoonValue(Generic[ValueT_co]):
    """will get value soon"""

    def __init__(self) -> None:
        self._value: ValueT_co | local = Pending

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
