from __future__ import annotations

import pytest

from .base import BaseTest, anyio_backend  # noqa: F401

pytest.importorskip("anyio")


@pytest.mark.anyio()
class TestAnyio(BaseTest):
    backend = "anyio"
