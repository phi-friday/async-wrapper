from __future__ import annotations

import time
from typing import Any

from typing_extensions import Self


class Timer:
    def __init__(self) -> None:
        self.start = 0
        self.end = 0

    def __enter__(self) -> Self:
        self.start = time.perf_counter()
        return self

    def __exit__(self, *args: Any) -> None:  # noqa: PYI036
        self.end = time.perf_counter()

    @property
    def term(self) -> float:
        if not self.end:
            raise RuntimeError("enter first")
        return self.end - self.start
