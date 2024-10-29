from __future__ import annotations

from functools import cached_property, partial, wraps
from typing import TYPE_CHECKING, Any, Generic

from anyio import to_thread
from typing_extensions import ParamSpec, TypeVar

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Coroutine

_T = TypeVar("_T", infer_variance=True)
_P = ParamSpec("_P")

__all__ = ["sync_to_async"]


class Async(Generic[_P, _T]):
    def __init__(self, func: Callable[_P, _T]) -> None:
        self._func = func

    @cached_property
    def _wrapped(self) -> Callable[_P, Coroutine[Any, Any, _T]]:
        @wraps(self._func)
        async def inner(*args: _P.args, **kwargs: _P.kwargs) -> _T:
            return await to_thread.run_sync(partial(self._func, *args, **kwargs))

        return inner

    async def __call__(self, *args: _P.args, **kwargs: _P.kwargs) -> _T:
        return await self._wrapped(*args, **kwargs)


def sync_to_async(func: Callable[_P, _T]) -> Callable[_P, Awaitable[_T]]:
    """
    Convert a synchronous function to an asynchronous function.

    Args:
        func: The synchronous function to be converted.

    Returns:
        An asynchronous function
        that behaves equivalently to the input synchronous function.

    Examples:
        ```python
        import time

        import anyio

        from async_wrapper import sync_to_async


        @sync_to_async
        def test(x: int) -> int:
            print(f"[{x}] test: start")
            time.sleep(1)
            print(f"[{x}] test: end")
            return x


        async def main() -> None:
            start = time.perf_counter()
            async with anyio.create_task_group() as task_group:
                for i in range(4):
                    task_group.start_soon(test, i)
            end = time.perf_counter()
            assert end - start < 1.1


        if __name__ == "__main__":
            anyio.run(main)
        ```
    """
    from async_wrapper.convert._sync.main import Sync

    if isinstance(func, Sync):
        return func._func  # noqa: SLF001
    return Async(func)
