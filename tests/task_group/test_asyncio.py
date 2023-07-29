from __future__ import annotations

import pytest

from .base import BaseTest

pytest.importorskip("asyncio")


@pytest.mark.asyncio()
class TestAnyio(BaseTest):
    backend = "asyncio"
