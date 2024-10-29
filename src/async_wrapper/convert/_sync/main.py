from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, wait
from contextvars import ContextVar
from functools import cached_property, partial, wraps
from importlib.util import find_spec
from typing import TYPE_CHECKING, Any, Generic, overload

import anyio
from sniffio import AsyncLibraryNotFoundError, current_async_library
from typing_extensions import ParamSpec, TypeVar

from async_wrapper.convert._sync.sqlalchemy import check_is_unset, run_sa_greenlet

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

_T = TypeVar("_T", infer_variance=True)
_P = ParamSpec("_P")

__all__ = ["async_to_sync"]

current_async_lib_var = ContextVar("current_async_lib", default="asyncio")
use_uvloop_var = ContextVar("use_uvloop", default=False)
has_sqlalchemy = (
    find_spec("sqlalchemy") is not None and find_spec("greenlet") is not None
)


class Sync(Generic[_P, _T]):
    def __init__(self, func: Callable[_P, Awaitable[_T]]) -> None:
        self._func = func

    @cached_property
    def _wrapped(self) -> Callable[_P, _T]:
        sync_func = _as_sync(self._func)

        @wraps(self._func)
        def inner(*args: _P.args, **kwargs: _P.kwargs) -> _T:
            if not _running_in_async_context():
                return _run(self._func, *args, **kwargs)

            backend = _get_current_backend()
            use_uvloop = _check_uvloop()

            with ThreadPoolExecutor(
                1, initializer=_init, initargs=(backend, use_uvloop)
            ) as pool:
                future = pool.submit(sync_func, *args, **kwargs)
                wait([future])
                return future.result()

        return inner

    def __call__(self, *args: _P.args, **kwargs: _P.kwargs) -> _T:
        return self._wrapped(*args, **kwargs)


@overload
def async_to_sync(
    func_or_awaitable: Callable[_P, Awaitable[_T]],
) -> Callable[_P, _T]: ...
@overload
def async_to_sync(func_or_awaitable: Awaitable[_T]) -> Callable[[], _T]: ...
@overload
def async_to_sync(
    func_or_awaitable: Callable[..., Awaitable[_T]] | Awaitable[_T],
) -> Callable[..., _T]: ...
def async_to_sync(
    func_or_awaitable: Callable[_P, Awaitable[_T]] | Awaitable[_T],
) -> Callable[_P, _T] | Callable[[], _T]:
    """
    Convert an awaitable function or awaitable object to a synchronous function.

    If used within an asynchronous context, attempts to use the same backend.
    Defaults to asyncio.

    Args:
        func_or_awaitable: An awaitable function or awaitable object.

    Returns:
        A synchronous function.

    Example:
        ```python
        import asyncio
        import time

        import anyio
        import sniffio

        from async_wrapper import async_to_sync


        @async_to_sync
        async def test(x: int) -> int:
            backend = sniffio.current_async_library()
            if backend == "asyncio":
                loop = asyncio.get_running_loop()
                print(backend, loop)
            else:
                print(backend)
            await anyio.sleep(1)
            return x


        def main() -> None:
            start = time.perf_counter()
            result = test(1)
            end = time.perf_counter()
            assert result == 1
            assert end - start < 1.1


        async def async_main() -> None:
            start = time.perf_counter()
            result = test(1)
            end = time.perf_counter()
            assert result == 1
            assert end - start < 1.1


        if __name__ == "__main__":
            main()
            anyio.run(
                async_main,
                backend="asyncio",
                backend_options={"use_uvloop": True},
            )
            anyio.run(
                async_main,
                backend="asyncio",
                backend_options={"use_uvloop": True},
            )
            anyio.run(async_main, backend="trio")
        ```
    """
    if callable(func_or_awaitable):
        from async_wrapper.convert._async import Async

        if isinstance(func_or_awaitable, Async):
            return func_or_awaitable._func  # noqa: SLF001
        return Sync(func_or_awaitable)

    if has_sqlalchemy:
        result = run_sa_greenlet(func_or_awaitable)
        if not check_is_unset(result):
            return result  # pyright: ignore[reportReturnType]

    awaitable_func = _awaitable_to_function(func_or_awaitable)
    return _async_func_to_sync(awaitable_func)


def _async_func_to_sync(func: Callable[_P, Awaitable[_T]]) -> Callable[_P, _T]:
    sync_func = _as_sync(func)

    @wraps(func)
    def inner(*args: _P.args, **kwargs: _P.kwargs) -> _T:
        if not _running_in_async_context():
            return _run(func, *args, **kwargs)

        backend = _get_current_backend()
        use_uvloop = _check_uvloop()

        with ThreadPoolExecutor(
            1, initializer=_init, initargs=(backend, use_uvloop)
        ) as pool:
            future = pool.submit(sync_func, *args, **kwargs)
            wait([future])
            return future.result()

    return inner


def _as_sync(func: Callable[_P, Awaitable[_T]]) -> Callable[_P, _T]:
    @wraps(func)
    def inner(*args: _P.args, **kwargs: _P.kwargs) -> _T:
        return _run(func, *args, **kwargs)

    return inner


def _run(func: Callable[_P, Awaitable[_T]], *args: _P.args, **kwargs: _P.kwargs) -> _T:
    backend = _get_current_backend()
    new_func = partial(func, *args, **kwargs)
    backend_options: dict[str, Any] = {}
    if backend == "asyncio":
        backend_options["use_uvloop"] = _check_uvloop()
    return anyio.run(new_func, backend=backend, backend_options=backend_options)


def _check_uvloop() -> bool:
    if use_uvloop_var.get():
        return True

    try:
        import uvloop
    except ImportError:  # pragma: no cover
        return False
    import asyncio

    policy = asyncio.get_event_loop_policy()
    return isinstance(policy, uvloop.EventLoopPolicy)


def _running_in_async_context() -> bool:
    try:
        current_async_library()
    except AsyncLibraryNotFoundError:
        return False
    return True


def _get_current_backend() -> str:
    try:
        return current_async_library()
    except AsyncLibraryNotFoundError:
        return current_async_lib_var.get()


def _init(backend: str, use_uvloop: bool) -> None:  # noqa: FBT001
    current_async_lib_var.set(backend)
    use_uvloop_var.set(use_uvloop)


def _awaitable_to_function(value: Awaitable[_T]) -> Callable[[], Awaitable[_T]]:
    async def awaitable() -> _T:
        return await value

    return awaitable
