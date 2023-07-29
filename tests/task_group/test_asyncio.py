from __future__ import annotations

import pytest

from .base import BaseTest

pytest.importorskip("asyncio")


@pytest.fixture(
    params=[
        pytest.param(("asyncio", {"use_uvloop": False}), id="asyncio"),
    ],
)
def anyio_backend(request):
    return request.param


@pytest.mark.anyio()
class TestAnyio(BaseTest):
    backend = "asyncio"
