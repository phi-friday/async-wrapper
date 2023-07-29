from __future__ import annotations

import pytest

from .base import BaseAsyncTest

pytest.importorskip("loky")


class TestLoky(BaseAsyncTest):
    backend = "loky"
