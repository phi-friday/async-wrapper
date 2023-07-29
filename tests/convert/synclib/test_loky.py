from __future__ import annotations

import pytest

from .base import BaseSyncTest

pytest.importorskip("loky")


class TestLoky(BaseSyncTest):
    backend = "loky"
