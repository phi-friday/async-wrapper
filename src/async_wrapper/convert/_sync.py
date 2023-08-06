from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, wait
from contextvars import ContextVar
from functools import partial, wraps
from typing import Awaitable, Callable, TypeVar

import anyio
from sniffio import AsyncLibraryNotFoundError, current_async_library
from typing_extensions import ParamSpec

ValueT_co = TypeVar("ValueT_co", covariant=True)
ParamT = ParamSpec("ParamT")

__all__ = ["async_to_sync"]

current_async_lib_var = ContextVar("current_async_lib", default="asyncio")
use_uvloop_var = ContextVar("use_uvloop", default=False)


def async_to_sync(
    func: Callable[ParamT, Awaitable[ValueT_co]],
) -> Callable[ParamT, ValueT_co]:
    """Convert an awaitable function to a synchronous function.

    If used within an asynchronous context, attempts to use the same backend.
    Defaults to asyncio.

    Args:
        func: An awaitable function.

    Returns:
        A synchronous function.

    Example:
        >>> import asyncio
        >>> import time
        >>>
        >>> import anyio
        >>> import sniffio
        >>>
        >>> from async_wrapper import async_to_sync
        >>>
        >>>
        >>> @async_to_sync
        >>> async def test(x: int) -> int:
        >>>     backend = sniffio.current_async_library()
        >>>     if backend == "asyncio":
        >>>         loop = asyncio.get_running_loop()
        >>>         print(backend, loop)
        >>>     else:
        >>>         print(backend)
        >>>     await anyio.sleep(1)
        >>>     return x
        >>>
        >>>
        >>> def main() -> None:
        >>>     start = time.perf_counter()
        >>>     result = test(1)
        >>>     end = time.perf_counter()
        >>>     assert result == 1
        >>>     assert end - start < 1.1
        >>>
        >>>
        >>> async def async_main() -> None:
        >>>     start = time.perf_counter()
        >>>     result = test(1)
        >>>     end = time.perf_counter()
        >>>     assert result == 1
        >>>     assert end - start < 1.1
        >>>
        >>>
        >>> if __name__ == "__main__":
        >>>     main()
        >>>     anyio.run(
        >>>         async_main,
        >>>         backend="asyncio",
        >>>         backend_options={"use_uvloop": True},
        >>>     )
        >>>     anyio.run(
        >>>         async_main,
        >>>         backend="asyncio",
        >>>         backend_options={"use_uvloop": True},
        >>>     )
        >>>     anyio.run(async_main, backend="trio")
        $ poetry run python main.py
        asyncio <_UnixSelectorEventLoop running=True closed=False debug=False>
        asyncio <_UnixSelectorEventLoop running=True closed=False debug=False>
        asyncio <uvloop.Loop running=True closed=False debug=False>
        trio
    """
    sync_func = _as_sync(func)

    @wraps(func)
    def inner(*args: ParamT.args, **kwargs: ParamT.kwargs) -> ValueT_co:
        backend = _get_current_backend()
        use_uvloop = _check_uvloop()
        with ThreadPoolExecutor(
            1,
            initializer=_init,
            initargs=(backend, use_uvloop),
        ) as pool:
            future = pool.submit(sync_func, *args, **kwargs)
            wait([future])
            return future.result()

    return inner


def _as_sync(
    func: Callable[ParamT, Awaitable[ValueT_co]],
) -> Callable[ParamT, ValueT_co]:
    @wraps(func)
    def inner(*args: ParamT.args, **kwargs: ParamT.kwargs) -> ValueT_co:
        return _run(func, *args, **kwargs)

    return inner


def _run(
    func: Callable[ParamT, Awaitable[ValueT_co]],
    *args: ParamT.args,
    **kwargs: ParamT.kwargs,
) -> ValueT_co:
    backend = _get_current_backend()
    new_func = partial(func, *args, **kwargs)
    backend_options = {}
    if backend == "asyncio":
        backend_options["use_uvloop"] = _check_uvloop()
    return anyio.run(new_func, backend=backend, backend_options=backend_options)


def _check_uvloop() -> bool:
    if use_uvloop_var.get():
        return True

    try:
        import uvloop  # type: ignore
    except ImportError:
        return False
    import asyncio

    policy = asyncio.get_event_loop_policy()
    return isinstance(policy, uvloop.EventLoopPolicy)


def _get_current_backend() -> str:
    try:
        return current_async_library()
    except AsyncLibraryNotFoundError:
        return current_async_lib_var.get()


def _init(backend: str, use_uvloop: bool) -> None:  # noqa: FBT001
    current_async_lib_var.set(backend)
    use_uvloop_var.set(use_uvloop)
