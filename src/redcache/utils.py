from __future__ import annotations

import sys
from base64 import b64encode
from inspect import getsource, isfunction, ismethod
from typing import TYPE_CHECKING, Any, Callable, Optional, TypeVar, Union

if sys.version_info < (3, 9):  # pragma: no cover
    import importlib_resources
else:  # pragma: no cover
    import importlib.resources as importlib_resources

if TYPE_CHECKING:  # pragma: no cover
    from hashlib import _Hash

__all__ = ["get_fullname", "get_source", "read_lua_file", "base64_hash_digest"]


def get_fullname(f: Callable) -> str:
    if isfunction(f):
        return f"{f.__module__}:{f.__qualname__}"
    elif ismethod(f):
        return f"{f.__module__}:{f.__class__}.{f.__qualname__}"
    raise TypeError(f"Can not calculate keys for {f=}")  # pragma: no cover


T = TypeVar("T")


def get_source(o: Any, default: Optional[T] = None) -> Union[str, T, None]:
    try:
        return getsource(o)
    except (IOError, OSError, TypeError):  # pragma: no cover
        return default  # pragma: no cover


def read_lua_file(file: str) -> str:
    return importlib_resources.files(__package__).joinpath("lua", file).read_text()


def base64_hash_digest(x: _Hash):
    return b64encode(x.digest()).rstrip(b"=")
