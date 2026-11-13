from collections.abc import Callable
from functools import wraps
from typing import Any, Literal, Protocol, cast, overload


class _Fn[Fst, **P, R](Protocol):
    def __call__(self, x: Fst, /, *args: P.args, **kwds: P.kwargs) -> R: ...


class Curried[Fst, **P, R](Protocol):
    @overload
    def __call__(self, arg: Fst, /, *args: P.args, **kwargs: P.kwargs) -> R: ...

    @overload
    def __call__(self, /, *args: P.args, **kwargs: P.kwargs) -> Callable[P, R]: ...

    def __call__(self, /, *args: Any, **kwargs: Any) -> Any: ...


def curry[T, **P, R](
    arity: Literal[1] = 1,
    /,
) -> Callable[[_Fn[T, P, R]], Curried[T, P, R]]:
    """
    Curry calling the first argument.
    """

    if arity != 1:
        raise ValueError("only arity 1 is supported for now.")

    def decorator(fn: _Fn[T, P, R]) -> Curried[T, P, R]:
        @wraps(fn)
        def wrapped(first: T, /, *args: P.args, **kwargs: P.kwargs):
            if args == (...,):
                return lambda *args, **kw: fn(first, *args, **{**kw, **kwargs})
            return fn(first, *args, **kwargs)

        return cast("Curried", wrapped)

    return decorator
