"""Handler system: protocol, registration validation, and invocation helpers.

A handler wraps the four serialization boundaries of the cache
(``before_serialize``, ``after_serialize``, ``before_deserialize``,
``after_deserialize``) and their ``*_async`` variants. Every method is
optional; the helpers in this module tolerate missing methods and the
async-to-sync fallback.
"""

from __future__ import annotations

from collections.abc import Callable
from inspect import isawaitable, iscoroutinefunction
from typing import Any, Protocol

from redis.typing import EncodedT, KeyT

__all__ = (
    "HandlerProtocol",
    "ainvoke_after",
    "ainvoke_before",
    "invoke_after",
    "invoke_before",
    "validate_handler",
)


class HandlerProtocol(Protocol):
    """Optional hooks around the four serialization boundaries.

    Every method is optional: a handler may implement any subset of them.
    Methods receive the value being processed plus keyword-only context.

    Return conventions:

    - ``before_serialize`` / ``before_deserialize`` return ``(handled, value)``.
    - ``after_serialize`` / ``after_deserialize`` return the replacement value
      directly; there is no default library step left for them to skip, so no
      ``handled`` flag is needed.

    The ``*_async`` variants are used by the asynchronous execution path. When
    an ``*_async`` method is absent, the asynchronous path falls back to the
    synchronous method of the same boundary (awaiting it if it is a coroutine).
    """

    def before_deserialize(
        self,
        value: EncodedT,
        *,
        keys: tuple[KeyT, KeyT],
        hash_value: KeyT,
        func: Callable | None = None,
        args: tuple | None = None,
        kwds: dict | None = None,
    ) -> tuple[bool, Any]: ...

    def after_deserialize(
        self,
        value: Any,
        *,
        keys: tuple[KeyT, KeyT],
        hash_value: KeyT,
        func: Callable | None = None,
        args: tuple | None = None,
        kwds: dict | None = None,
    ) -> Any: ...

    def before_serialize(
        self,
        value: Any,
        *,
        keys: tuple[KeyT, KeyT],
        hash_value: KeyT,
        func: Callable | None = None,
        args: tuple | None = None,
        kwds: dict | None = None,
    ) -> tuple[bool, Any]: ...

    def after_serialize(
        self,
        value: EncodedT,
        *,
        keys: tuple[KeyT, KeyT],
        hash_value: KeyT,
        func: Callable | None = None,
        args: tuple | None = None,
        kwds: dict | None = None,
    ) -> Any: ...

    async def before_deserialize_async(
        self,
        value: EncodedT,
        *,
        keys: tuple[KeyT, KeyT],
        hash_value: KeyT,
        func: Callable | None = None,
        args: tuple | None = None,
        kwds: dict | None = None,
    ) -> tuple[bool, Any]: ...

    async def after_deserialize_async(
        self,
        value: Any,
        *,
        keys: tuple[KeyT, KeyT],
        hash_value: KeyT,
        func: Callable | None = None,
        args: tuple | None = None,
        kwds: dict | None = None,
    ) -> Any: ...

    async def before_serialize_async(
        self,
        value: Any,
        *,
        keys: tuple[KeyT, KeyT],
        hash_value: KeyT,
        func: Callable | None = None,
        args: tuple | None = None,
        kwds: dict | None = None,
    ) -> tuple[bool, Any]: ...

    async def after_serialize_async(
        self,
        value: EncodedT,
        *,
        keys: tuple[KeyT, KeyT],
        hash_value: KeyT,
        func: Callable | None = None,
        args: tuple | None = None,
        kwds: dict | None = None,
    ) -> Any: ...


_HANDLER_SYNC_METHODS = (
    "before_serialize",
    "after_serialize",
    "before_deserialize",
    "after_deserialize",
)


def validate_handler(handler: HandlerProtocol | None) -> None:
    """Validate handler method shapes at registration time.

    Synchronous methods must not be coroutine functions because the
    synchronous execution path calls them without awaiting. ``*_async``
    methods must be coroutine functions because the asynchronous path
    awaits them directly.
    """
    if handler is None:
        return
    for name in _HANDLER_SYNC_METHODS:
        sync_method = getattr(handler, name, None)
        if sync_method is not None and iscoroutinefunction(sync_method):
            raise TypeError(
                f"handler.{name} must not be a coroutine function; define {name}_async for asynchronous handling"
            )
        async_method = getattr(handler, f"{name}_async", None)
        if async_method is not None and not iscoroutinefunction(async_method):
            raise TypeError(f"handler.{name}_async must be a coroutine function")


def invoke_before(handler: Any, method_name: str, value: Any, ctx: dict[str, Any]) -> tuple[bool, Any]:
    """Call ``handler.<method_name>`` if present, else ``(False, value)``."""
    method = getattr(handler, method_name, None) if handler is not None else None
    if method is None:
        return False, value
    return method(value, **ctx)


def invoke_after(handler: Any, method_name: str, value: Any, ctx: dict[str, Any]) -> Any:
    """Call ``handler.<method_name>`` if present, else ``value``."""
    method = getattr(handler, method_name, None) if handler is not None else None
    if method is None:
        return value
    return method(value, **ctx)


async def ainvoke_before(handler: Any, method_name: str, value: Any, ctx: dict[str, Any]) -> tuple[bool, Any]:
    """Async variant of :func:`invoke_before`.

    Prefers ``<method_name>_async``; falls back to the synchronous method,
    awaiting it when it returns an awaitable.
    """
    if handler is None:
        return False, value
    method = getattr(handler, f"{method_name}_async", None) or getattr(handler, method_name, None)
    if method is None:
        return False, value
    result = method(value, **ctx)
    if isawaitable(result):
        result = await result
    return result


async def ainvoke_after(handler: Any, method_name: str, value: Any, ctx: dict[str, Any]) -> Any:
    """Async variant of :func:`invoke_after`.

    Prefers ``<method_name>_async``; falls back to the synchronous method,
    awaiting it when it returns an awaitable.
    """
    if handler is None:
        return value
    method = getattr(handler, f"{method_name}_async", None) or getattr(handler, method_name, None)
    if method is None:
        return value
    result = method(value, **ctx)
    if isawaitable(result):
        result = await result
    return result
