from __future__ import annotations

import pytest

from .base import BaseTest


@pytest.mark.anyio()
class TestAnyio(BaseTest):
    backend = "anyio"
