from inspect import getsource, isfunction, ismethod
from typing import Any, Callable, TypeVar, Union

__all__ = ["get_fullname", "get_source"]


def get_fullname(f: Callable) -> str:
    if isfunction(f):
        return f"{f.__module__}:{f.__qualname__}"
    elif ismethod(f):
        return f"{f.__module__}:{f.__class__}.{f.__qualname__}"
    raise TypeError(f"Can not calculate keys for {f=}")


T = TypeVar("T")


def get_source(o: Any, default: T = None) -> Union[str, T]:
    try:
        return getsource(o)
    except (IOError, OSError, TypeError):
        return default
