from __future__ import annotations

__all__ = [
    "PendingError",
    "QueueError",
    "QueueEmptyError",
    "QueueFullError",
    "QueueBrokenError",
]


class PendingError(Exception):
    """Exception used exclusively for pending values.

    This exception is used within the context of handling soon values.
    """


class QueueError(Exception):
    """Base exception for queue-related errors.

    This exception serves as the base class for various queue-related exceptions.
    """


class QueueEmptyError(QueueError):
    """Exception raised when attempting to retrieve an item from an empty queue.

    This exception occurs when trying to get an item from a queue
    that has no available items.
    """


class QueueFullError(QueueError):
    """Exception raised when attempting to add an item to a full queue.

    This exception occurs when trying to put an item into a queue
    that has reached its capacity.
    """


class QueueBrokenError(QueueError):
    """Exception raised when attempting to operate on a closed queue.

    This exception is raised when trying to get or put an item into a closed queue.
    """
