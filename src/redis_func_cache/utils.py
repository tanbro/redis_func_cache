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


__all__ = ("b64digest", "get_callable_bytecode", "read_lua_file", "clean_lua_script")


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


def get_callable_bytecode(obj: Callable) -> bytes:
    """Retrieve the bytecode of the given callable object.

    Args:
        obj: The function to retrieve bytecode from.

    Returns:
        The bytecode of the function, or `b""` the function has no `__code__` attribute.
    """
    try:
        return obj.__code__.co_code
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
    return dedent(importlib_resources.files(__package__).joinpath("lua").joinpath(file).read_text("utf-8")).strip()


def clean_lua_script(source: str) -> str:
    """Remove comments and empty lines from a Lua script.

    Args:
        source: The Lua script source code to be cleaned.

    Returns:
        The cleaned Lua script as a string.

    Note:
        This function utilizes the :mod:`pygments` library to remove comments and empty lines from the Lua script.
        If :mod:`pygments` is not installed, the source code will be returned unchanged.
    """
    try:
        from pygments.filter import simplefilter
        from pygments.lexers import get_lexer_by_name
        from pygments.token import Comment, String
    except ImportError:
        return source
    else:
        filter_types = (
            String.Doc,
            Comment,
            Comment.Hashbang,
            Comment.Multiline,
            Comment.Preproc,
            Comment.PreprocFile,
            Comment.Single,
            Comment.Special,
        )

        @simplefilter
        def filter(self, lexer, stream, options):
            yield from ((ttype, value) for ttype, value in stream if ttype not in filter_types)

        lexer = get_lexer_by_name("lua")
        lexer.add_filter(filter())  # pyright: ignore[reportCallIssue]

        code = ""
        for tok_type, tok_str in lexer.get_tokens(source):
            code += tok_str

        result = ""
        for line in code.splitlines():
            if line_stripped := line.strip():
                result += line_stripped + "\n"

        return result
