from __future__ import annotations

from .base import BaseSyncTest


class TestThread(BaseSyncTest):
    backend = "thread"
