import sys
from inspect import getsource, isfunction, ismethod
from typing import Any, Callable, Optional, TypeVar, Union

if sys.version_info < (3, 9):  # pragma: no cover
    import importlib_resources
else:  # pragma: no cover
    import importlib.resources as importlib_resources

__all__ = ["get_fullname", "get_source", "read_lua_file"]


def get_fullname(f: Callable) -> str:
    if isfunction(f):
        return f"{f.__module__}:{f.__qualname__}"
    elif ismethod(f):
        return f"{f.__module__}:{f.__class__}.{f.__qualname__}"
    raise TypeError(f"Can not calculate keys for {f=}")


T = TypeVar("T")


def get_source(o: Any, default: Optional[T] = None) -> Union[str, T, None]:
    try:
        return getsource(o)
    except (IOError, OSError, TypeError):
        return default


def read_lua_file(file: str) -> str:
    return importlib_resources.files(__package__).joinpath("lua", file).read_text()
