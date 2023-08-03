from __future__ import annotations

__all__ = [
    "PendingError",
    "QueueError",
    "QueueEmptyError",
    "QueueFullError",
    "QueueBrokenError",
]


class PendingError(Exception):
    """using only in soon value"""


class QueueError(Exception):
    """using only in Queue"""


class QueueEmptyError(QueueError):
    """try to get an item when queue is empty"""


class QueueFullError(QueueError):
    """try to put an item when queue is full"""


class QueueBrokenError(QueueError):
    """try to get or put an item when queue is closed"""
