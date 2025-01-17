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
    """Clean a Lua script by removing comments and empty lines.

    Args:
        source: The source code of the Lua script to clean.

    Returns:
        The cleaned Lua file as a string.
    """
    try:
        from pygments.filter import simplefilter
        from pygments.lexers import get_lexer_by_name
        from pygments.token import Comment, String
    except ImportError:
        return source
    else:

        @simplefilter
        def no_comment(self, lexer, stream, options):
            yield from (
                (ttype, value)
                for ttype, value in stream
                if not (
                    any(
                        ttype is t_
                        for t_ in (
                            Comment,
                            Comment.Hashbang,
                            Comment.Multiline,
                            Comment.Preproc,
                            Comment.PreprocFile,
                            Comment.Single,
                            Comment.Special,
                        )
                    )
                )
            )

        @simplefilter
        def no_docstring(self, lexer, stream, options):
            yield from ((ttype, value) for ttype, value in stream if ttype is not String.Doc)

        lexer = get_lexer_by_name("lua")
        lexer.add_filter(no_comment())  # pyright: ignore[reportCallIssue]
        lexer.add_filter(no_docstring())  # pyright: ignore[reportCallIssue]

        lines_iter = (line for line in "".join(s for _, s in lexer.get_tokens(source)).splitlines() if line.strip())
        return "\n".join(lines_iter)
