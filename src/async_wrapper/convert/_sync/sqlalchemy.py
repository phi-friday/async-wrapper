from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING, Any

from typing_extensions import TypeGuard, TypeVar

if TYPE_CHECKING:
    from collections.abc import Awaitable

    import greenlet


_T = TypeVar("_T", infer_variance=True)
_SA_GREENLET_ATTR = "__sqlalchemy_greenlet_provider__"


class Unset: ...


unset = Unset()


def _check_sa_greenlet(green: greenlet.greenlet) -> bool:
    return getattr(green, _SA_GREENLET_ATTR, False) is True


def _check_sa_current_greenlet() -> bool:
    try:
        import greenlet
    except ImportError as exc:  # pragma: no cover
        error_msg = (
            "Please install the dependencies "
            "by running 'pip install async_wrapper[sqlalchemy]'."
        )
        raise ImportError(error_msg) from exc
    current = greenlet.getcurrent()
    return _check_sa_greenlet(current)


def run_sa_greenlet(awaitable: Awaitable[_T]) -> _T | Unset:
    with suppress(ImportError):
        if _check_sa_current_greenlet():
            return _wait_sa_greenlet(awaitable)

    return unset


def _wait_sa_greenlet(awaitable: Awaitable[_T]) -> _T:
    try:
        from sqlalchemy.util import await_only
    except ImportError as exc:  # pragma: no cover
        error_msg = (
            "Please install the dependencies "
            "by running 'pip install async_wrapper[sqlalchemy]'."
        )
        raise ImportError(error_msg) from exc
    return await_only(awaitable)


def check_is_unset(value: Any) -> TypeGuard[Unset]:
    return value is unset
