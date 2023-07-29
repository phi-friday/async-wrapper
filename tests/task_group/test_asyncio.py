from __future__ import annotations

import pytest

from .base import BaseTest, anyio_backend  # noqa: F401

pytest.importorskip("asyncio")


@pytest.mark.asyncio()
class TestAnyio(BaseTest):
    backend = "asyncio"
