"""Handler system: protocol and call context.

A handler intervenes at the four serialization boundaries of the cache —
before/after the library serializes a value on the write path, and
before/after it deserializes bytes on the read path — with paired sync and
``*_async`` methods for the two execution paths.

:class:`HandlerProtocol` is a pure structural protocol: it carries no
implementations. An implementation conforms by matching its signatures;
the type annotations are the contract, enforced by static checking.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from typing import Protocol

from redis.typing import EncodableT, EncodedT, KeyT

__all__ = (
    "HandlerContext",
    "HandlerProtocol",
)


@dataclass(frozen=True)
class HandlerContext:
    """Immutable context passed to every handler method.

    Attributes:
        keys: The ``(zset_key, hash_key)`` pair for this cache entry.
        hash_value: The hash field for this invocation.
        func: The decorated function.
        args: The effective positional arguments, i.e. the arguments used
            for cache key calculation (after ``excludes`` filtering when
            :meth:`RedisFuncCache.decorate` was called with ``excludes``).
        kwds: The effective keyword arguments, same filtering as ``args``.
    """

    keys: tuple[KeyT, KeyT]
    hash_value: KeyT
    func: Callable | None
    args: tuple = ()
    kwds: dict = field(default_factory=dict)


if TYPE_CHECKING:

    class HandlerProtocol(Protocol):
        """Extension points around the four serialization boundaries of the cache.

        The cache converts every cached value twice on each full cycle:

        - **Write path** (cache miss): the user function's return value is
        *serialized* into bytes stored in Redis.
        - **Read path** (cache hit): those bytes are *deserialized* back into
        the value returned to the caller.

        A handler may intervene at up to four points — before and after each of
        the two conversions. The four intervention points have distinct jobs:

        - ``before_serialize``: replace the value the library is about to
        serialize, or take over the write entirely by returning ready-made
        bytes.
        - ``after_serialize``: post-process the serialized bytes (e.g. compress,
        encrypt, prefix) before they are written to Redis.
        - ``before_deserialize``: replace the raw bytes the library is about to
        deserialize, or take over the read entirely by returning the final
        value.
        - ``after_deserialize``: post-process the deserialized value (e.g.
        enrich, validate, convert) before it is returned to the caller.

        Each boundary exists in two flavors, forming two groups: the plain
        names serve the synchronous execution path, the ``*_async`` coroutine
        functions serve the asynchronous path. There is no fallback between
        them. An implementation provides at least one group — the one its
        execution path uses — and the other group, if unused, may be kept as
        ``raise NotImplementedError`` placeholders. Within a provided group
        every method is defined; a method with nothing to do still returns
        explicitly, passing its input through unchanged (see the return
        conventions below).

        Return conventions differ between the two halves:

        - A ``before_*`` method returns a ``(handled, value)`` pair. ``value``
        always replaces the value flowing through that point. ``handled``
        states whether the implementation performed the library's job itself:
        when true, the library skips its own conversion **and every later
        step on that path** (including the corresponding ``after_*`` method);
        when false, the library continues with ``value``. A method with
        nothing to do returns ``(False, value)`` — explicitly unhandled,
        with its input unchanged — so the library's default step runs as
        usual.
        - An ``after_*`` method returns the replacement value directly — there
        is no library step left after it, so there is nothing for a
        ``handled`` flag to control. A method with nothing to do returns
        its input unchanged.

        Every method receives the value at that point as its first positional
        argument, plus the :class:`HandlerContext` of the current invocation as
        a keyword-only ``ctx`` argument. The protocol is purely structural: an
        implementation does not need to inherit from this class.
        """

        def before_serialize(self, value: Any, *, ctx: HandlerContext) -> tuple[bool, Any]:
            """Intervene on the write path before the library serializes ``value``.

            Args:
                value: The user function's return value, about to be serialized.
                ctx: The invocation context.

            Returns:
                A ``(handled, value)`` pair. ``value`` replaces the value to be
                stored. If ``handled`` is true, ``value`` must already be bytes
                (or a str accepted by Redis); the library skips its serializer
                and ``after_serialize`` and writes ``value`` as-is. If false,
                the library serializes ``value`` and proceeds to
                ``after_serialize``. A method with nothing to do returns
                ``(False, value)`` unchanged.
            """
            ...

        def after_serialize(self, value: EncodableT, *, ctx: HandlerContext) -> Any:
            """Post-process the serialized bytes before they are written to Redis.

            Only invoked when ``before_serialize`` did not take over the write.

            Args:
                value: The serialized bytes produced by the library.
                ctx: The invocation context.

            Returns:
                The replacement bytes to store in Redis. A method with nothing
                to do returns ``value`` unchanged.
            """
            ...

        def before_deserialize(self, value: EncodedT, *, ctx: HandlerContext) -> tuple[bool, Any]:
            """Intervene on the read path before the library deserializes the cached bytes.

            Args:
                value: The raw bytes read from Redis (cache hit only).
                ctx: The invocation context.

            Returns:
                A ``(handled, value)`` pair. ``value`` replaces the bytes to be
                deserialized. If ``handled`` is true, ``value`` is the **final**
                result returned to the caller; the library skips its
                deserializer and ``after_deserialize``. If false, the library
                deserializes ``value`` and proceeds to ``after_deserialize``.
                A method with nothing to do returns ``(False, value)`` unchanged.
            """
            ...

        def after_deserialize(self, value: Any, *, ctx: HandlerContext) -> Any:
            """Post-process the deserialized value before it is returned to the caller.

            Only invoked when ``before_deserialize`` did not take over the read.

            Args:
                value: The value produced by the library's deserializer.
                ctx: The invocation context.

            Returns:
                The replacement value to return to the caller. A method with
                nothing to do returns ``value`` unchanged.
            """
            ...

        async def before_serialize_async(self, value: Any, *, ctx: HandlerContext) -> tuple[bool, Any]:
            """Async-path counterpart of :meth:`before_serialize` (coroutine function)."""
            ...

        async def after_serialize_async(self, value: EncodableT, *, ctx: HandlerContext) -> Any:
            """Async-path counterpart of :meth:`after_serialize` (coroutine function)."""

        async def before_deserialize_async(self, value: EncodedT, *, ctx: HandlerContext) -> tuple[bool, Any]:
            """Async-path counterpart of :meth:`before_deserialize` (coroutine function)."""
            ...

        async def after_deserialize_async(self, value: Any, *, ctx: HandlerContext) -> Any:
            """Async-path counterpart of :meth:`after_deserialize` (coroutine function)."""
            ...
