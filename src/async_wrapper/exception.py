from __future__ import annotations

__all__ = [
    "PendingError",
    "QueueError",
    "QueueEmptyError",
    "QueueFullError",
    "QueueClosedError",
    "QueueBrokenError",
    "QueueRestrictedError",
    "DisposableError",
    "AlreadyDisposedError",
]


class PendingError(Exception):
    """
    Exception used exclusively for pending values.

    This exception is used within the context of handling soon values.
    """


class QueueError(Exception):
    """
    Base exception for queue-related errors.

    This exception serves as the base class for various queue-related exceptions.
    """


class QueueEmptyError(QueueError):
    """
    Exception raised when attempting to retrieve an item from an empty queue.

    This exception occurs when trying to get an item from a queue
    that has no available items.
    """


class QueueFullError(QueueError):
    """
    Exception raised when attempting to add an item to a full queue.

    This exception occurs when trying to put an item into a queue
    that has reached its capacity.
    """


class QueueClosedError(QueueError):
    """
    Error that occurs when attempting to get from or put into a closed queue.

    This error is different from QueueBrokenError.
        :exc:`QueueBrokenError` is an unintended error.

        :exc:`QueueClosedError` is an error deliberately raised.
    """


class QueueBrokenError(QueueError):
    """
    Error that occurs when trying to get from or put into a closed queue.

    This error is different from QueueClosedError.
        :exc:`QueueClosedError` is an error deliberately raised.

        :exc:`QueueBrokenError` is an unintended error.
    """


class QueueRestrictedError(QueueError):
    """queue is restricted but used"""


class DisposableError(Exception):
    """
    Base exception for disposable-related errors.

    This exception serves as the base class for various disposable-related exceptions.
    """


class AlreadyDisposedError(DisposableError):
    """Indicates that an attempt was made to use a disposable that has already been disposed of."""  # noqa: E501
