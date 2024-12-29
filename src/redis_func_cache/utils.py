from __future__ import annotations

import sys
from base64 import b64encode
from inspect import getsource
from typing import TYPE_CHECKING, Any, Callable, Optional, TypeVar, Union

if sys.version_info < (3, 9):  # pragma: no cover
    import importlib_resources
else:  # pragma: no cover
    import importlib.resources as importlib_resources

if TYPE_CHECKING:  # pragma: no cover
    from hashlib import _Hash

__all__ = ["get_fullname", "get_source", "read_lua_file", "base64_hash_digest"]


def get_fullname(f: Callable) -> str:
    """Get the full name of a callable object.

    Includes the module name and the qualified name.
    """
    return f"{f.__module__}:{f.__qualname__}"


DefaultT = TypeVar("DefaultT")


def get_source(o: Any, default: Optional[DefaultT] = None) -> Union[str, DefaultT, None]:
    """Get the source code of a callable object.

    This function attempts to obtain the source code of a given callable object. If it cannot access the source code,
    it returns a default value. This is useful when dealing with objects whose source code may not be directly accessible,
    such as built-in functions or objects defined in interactive interpreters.

    Args:
        o: The callable object whose source code is to be retrieved.

        default: The default value to return if the source code cannot be retrieved.

            This provides a fallback mechanism to handle cases where the source code is not available.

    Returns:
        The source code of the object as a string, or the default value if the source code cannot be retrieved.
        If no default value is provided and the source code cannot be retrieved, it returns ``None``.
    """
    try:
        return getsource(o)
    except (IOError, OSError, TypeError):
        return default


def read_lua_file(file: str) -> str:
    """Read a Lua file from the package resources.

    Args:
        file: The name of the Lua file to read.

    Returns:
        The contents of the Lua file as a string.


    This function locates and reads the entire text content of a specified Lua file.
    It uses the :mod:`importlib.resources` to locate the file.
    """
    return importlib_resources.files(__package__).joinpath("lua").joinpath(file).read_text()


def base64_hash_digest(x: _Hash) -> bytes:
    """Convert hash digest to base64 string.

    Args:
        x: The hash object.

    Returns:
        The base64 encoded digest of the hash object.

    This function takes a hash object (e.g., SHA256, MD5, etc.) and returns its digest,
    encoded in Base64 format.

    It is useful when you need to represent a hash value in a compact and readable format.
    """
    return b64encode(x.digest()).rstrip(b"=")
