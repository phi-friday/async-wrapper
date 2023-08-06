from __future__ import annotations

from functools import partial, wraps
from typing import Any, Callable, Coroutine, TypeVar

import anyio
from typing_extensions import ParamSpec

ValueT_co = TypeVar("ValueT_co", covariant=True)
ParamT = ParamSpec("ParamT")

__all__ = ["sync_to_async"]


def sync_to_async(
    func: Callable[ParamT, ValueT_co],
) -> Callable[ParamT, Coroutine[Any, Any, ValueT_co]]:
    """Convert a synchronous function to an asynchronous function.

    Args:
        func: The synchronous function to be converted.

    Returns:
        An asynchronous function
        that behaves equivalently to the input synchronous function.

    Note:
        how to use:
        >>> import time
        >>>
        >>> import anyio
        >>>
        >>> from async_wrapper import sync_to_async
        >>>
        >>>
        >>> @sync_to_async
        >>> def test(x: int) -> int:
        >>>     print(f"[{x}] test: start")
        >>>     time.sleep(1)
        >>>     print(f"[{x}] test: end")
        >>>     return x
        >>>
        >>>
        >>> async def main() -> None:
        >>>     start = time.perf_counter()
        >>>     async with anyio.create_task_group() as task_group:
        >>>         for i in range(4):
        >>>             task_group.start_soon(test, i)
        >>>     end = time.perf_counter()
        >>>     assert end - start < 1.1
        >>>
        >>>
        >>> if __name__ == "__main__":
        >>>     anyio.run(main)
    """

    @wraps(func)
    async def inner(*args: ParamT.args, **kwargs: ParamT.kwargs) -> ValueT_co:
        return await anyio.to_thread.run_sync(partial(func, *args, **kwargs))

    return inner
