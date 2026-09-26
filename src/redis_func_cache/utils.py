from __future__ import annotations

import importlib.resources
import types
from base64 import b64encode
from collections.abc import Callable
from functools import lru_cache
from textwrap import dedent
from typing import TYPE_CHECKING
from warnings import warn

if TYPE_CHECKING:  # pragma: no cover
    from hashlib import _Hash as HashT

try:  # pragma: no cover
    import pygments  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    pygments = None  # type: ignore[assignment]
    LUA_PYGMENTS_FILTER_TYPES = None
else:  # pragma: no cover
    from pygments.filter import simplefilter
    from pygments.lexers import get_lexer_by_name
    from pygments.token import Comment, String

    LUA_PYGMENTS_FILTER_TYPES = (
        String.Doc,
        Comment,
        Comment.Hashbang,
        Comment.Multiline,
        Comment.Preproc,
        Comment.PreprocFile,
        Comment.Single,
        Comment.Special,
    )

from .typing import is_module

__all__ = ("b64digest", "get_callable_bytecode", "read_lua_file")


def b64digest(x: HashT) -> bytes:
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


@lru_cache
def calculate_callable_fullname(val: Callable) -> str:
    if not callable(val):
        raise TypeError("object must be callable")
    if isinstance(val, staticmethod):
        val = val.__func__
    if isinstance(val, types.FunctionType):
        module, qualname = val.__module__, val.__qualname__
    elif isinstance(val, types.MethodType) and isinstance(val.__self__, type):
        func = val.__func__
        if not isinstance(func, types.FunctionType):
            raise TypeError(f"Unsupported method {val!r}")
        module = func.__module__
        qualname = f"{val.__self__.__qualname__}.{func.__name__}"
    else:
        raise TypeError(
            f"Can not calculate a stable cross-process hash for {type(val).__name__}. "
            "Only functions, static methods and class methods are supported. "
            "Wrap it in a plain function, or use excludes/excludes_positional for methods."
        )
    return f"{module}:{qualname}"


@lru_cache
def get_callable_bytecode(val: Callable) -> bytes:
    """Retrieve the bytecode of the given callable object.

    Args:
        obj: The function to retrieve bytecode from.

    Returns:
        The bytecode of the function, or `b""` if the function has no `__code__` attribute.
    """
    if not callable(val):
        raise TypeError("object must be callable")
    if isinstance(val, staticmethod):
        val = val.__func__
    # Function objects have a `__code__` attribute, but not all callable objects are functions
    try:
        return val.__code__.co_code  # type: ignore
    except AttributeError:
        return b""


@lru_cache
def read_lua_file(file: str) -> str:
    """Read a Lua file from the package resources.

    Args:
        file: The name of the Lua file to read.

    Returns:
        The contents of the Lua file as a string.

    Note:
        - This function locates and reads the entire text content of a specified Lua file.
          It uses the :mod:`importlib.resources` to locate the file.
        - This function utilizes the :mod:`pygments` library to remove comments and empty lines from the Lua script.
          If :mod:`pygments` is not installed, the source code will be returned unchanged.
    """
    if __package__ is None:
        raise RuntimeError("__package__ is None")
    source = dedent(importlib.resources.files(__package__).joinpath("lua").joinpath(file).read_text("utf-8")).strip()
    if is_module(pygments):  # pragma: no cover
        lexer = get_lexer_by_name("lua")  # pyright: ignore[reportPossiblyUnboundVariable]
        if lexer is None:  # pragma: no cover
            warn("Lua lexer not found in pygments, return source code as is", RuntimeWarning)
            return source
        lexer.add_filter(_filter())  # pyright: ignore[reportCallIssue]
        code = "".join(tok_str for _, tok_str in lexer.get_tokens(source))
        # remote empty lines
        return "\n".join(s for line in code.splitlines() if (s := line.strip()))
    return source


if is_module(pygments):

    @simplefilter  # pyright: ignore[reportPossiblyUnboundVariable]
    def _filter(self, lexer, stream, options):
        if LUA_PYGMENTS_FILTER_TYPES is None:
            raise RuntimeError("‘LUA_PYGMENTS_FILTER_TYPES’ is None")
        yield from ((ttype, value) for ttype, value in stream if ttype not in LUA_PYGMENTS_FILTER_TYPES)
