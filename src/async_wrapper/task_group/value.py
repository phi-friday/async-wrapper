from __future__ import annotations

from threading import local
from typing import Generic, TypeVar

from async_wrapper.exception import PendingError

ValueT_co = TypeVar("ValueT_co", covariant=True)
Pending = local()

__all__ = ["SoonValue"]


class SoonValue(Generic[ValueT_co]):
    """A class representing a value that will be available soon."""

    __slots__ = ("_value",)

    def __init__(self) -> None:
        self._value: ValueT_co | local = Pending

    def __repr__(self) -> str:
        status = "pending" if self._value is Pending else "done"
        return f"<SoonValue: status={status}>"

    @property
    def value(self) -> ValueT_co:
        """
        Gets the soon-to-be available value.

        Raises:
            PendingError: Raised if the value is not yet available.

        Returns:
            The soon-to-be available value.
        """
        if self._value is Pending:
            raise PendingError
        return self._value  # type: ignore

    @property
    def is_ready(self) -> bool:
        """
        Checks if the value is ready.

        Returns:
            True if the value is not pending, False otherwise.
        """
        return self._value is not Pending
