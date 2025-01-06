from __future__ import annotations

import sys
from base64 import b64encode
from textwrap import dedent
from typing import TYPE_CHECKING, Callable

if sys.version_info < (3, 9):  # pragma: no cover
    import importlib_resources
else:  # pragma: no cover
    import importlib.resources as importlib_resources

if TYPE_CHECKING:  # pragma: no cover
    from hashlib import _Hash


__all__ = ("b64digest", "get_function_code", "read_lua_file")


def b64digest(x: _Hash) -> bytes:
    """Convert hash digest to base64 string.

    Args:
        x: The hash object.

    Returns:
        The base64 encoded digest of the hash object.

    This function takes a hash object (e.g., SHA256, MD5, etc.) and returns its digest,
    encoded in Base64 format, with `"="` paddings stripped.

    It is useful when you need to represent a hash value in a compact and readable format.
    """
    return b64encode(x.digest()).rstrip(b"=")


def get_function_code(f: Callable) -> bytes:
    """Retrieve the bytecode of the given function.

    Args:
        f: The function to retrieve bytecode from.

    Returns:
        The bytecode of the function, or `b""` the function has no `__code__` attribute.
    """
    try:
        return f.__code__.co_code
    except AttributeError:
        return b""


def read_lua_file(file: str) -> str:
    """Read a Lua file from the package resources.

    Args:
        file: The name of the Lua file to read.

    Returns:
        The contents of the Lua file as a string.


    This function locates and reads the entire text content of a specified Lua file.
    It uses the :mod:`importlib.resources` to locate the file.
    """
    return dedent(importlib_resources.files(__package__).joinpath("lua").joinpath(file).read_text()).strip()
