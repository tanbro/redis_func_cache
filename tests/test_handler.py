"""Tests for the handler system (four serialization boundaries)."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import patch

import pytest
import pytest_asyncio

from redis_func_cache import HandlerProtocol, LruPolicy, RedisFuncCache

from ._catches import ASYNC_REDIS_FACTORY, REDIS_FACTORY


class RecordingHandler:
    """A handler that records every call and returns configurable results."""

    def __init__(self, results: dict[str, Any] | None = None):
        self.calls: list[tuple[str, Any]] = []
        self.results = results or {}

    def _result(self, name: str, default: Any) -> Any:
        if name in self.results:
            return self.results[name]
        return default

    def before_serialize(self, value, **kwargs):
        self.calls.append(("before_serialize", value))
        return self._result("before_serialize", (False, value))

    def after_serialize(self, value, **kwargs):
        self.calls.append(("after_serialize", value))
        result = self._result("after_serialize", value)
        return result

    def before_deserialize(self, value, **kwargs):
        self.calls.append(("before_deserialize", value))
        return self._result("before_deserialize", (False, value))

    def after_deserialize(self, value, **kwargs):
        self.calls.append(("after_deserialize", value))
        return self._result("after_deserialize", value)


class AsyncRecordingHandler:
    """Async variant of :class:`RecordingHandler`."""

    def __init__(self, results: dict[str, Any] | None = None):
        self.calls: list[tuple[str, Any]] = []
        self.results = results or {}

    def _result(self, name: str, default: Any) -> Any:
        if name in self.results:
            return self.results[name]
        return default

    async def before_serialize_async(self, value, **kwargs):
        self.calls.append(("before_serialize", value))
        return self._result("before_serialize", (False, value))

    async def after_serialize_async(self, value, **kwargs):
        self.calls.append(("after_serialize", value))
        return self._result("after_serialize", value)

    async def before_deserialize_async(self, value, **kwargs):
        self.calls.append(("before_deserialize", value))
        return self._result("before_deserialize", (False, value))

    async def after_deserialize_async(self, value, **kwargs):
        self.calls.append(("after_deserialize", value))
        return self._result("after_deserialize", value)


def _make_cache(handler=None) -> RedisFuncCache:
    return RedisFuncCache("handler_test", LruPolicy(), factory=REDIS_FACTORY, handler=handler)


def _make_async_cache(handler=None) -> RedisFuncCache:
    return RedisFuncCache("handler_test_async", LruPolicy(), factory=ASYNC_REDIS_FACTORY, handler=handler)


@pytest.fixture
def cache():
    c = _make_cache()
    yield c
    c.policy.purge(redis_client=c.get_redis_client())


@pytest_asyncio.fixture
async def async_cache():
    c = _make_async_cache()
    yield c
    await c.policy.apurge(redis_client=c.get_redis_client())


def _captured_put_value(cache: RedisFuncCache, invoke) -> Any:
    """Run ``invoke`` and return the value passed to ``cache.put``."""
    with patch.object(cache, "put") as mock_put:
        invoke()
        mock_put.assert_called_once()
        return mock_put.call_args[0][3]


def test_no_handler_unchanged(cache: RedisFuncCache):
    """Without a handler, behavior is identical to before."""

    @cache
    def echo(x):
        return {"value": x}

    assert echo(1) == {"value": 1}
    assert echo(1) == {"value": 1}


def test_before_serialize_handled_false_uses_returned_value():
    """handled=False: library serializes the handler's returned value."""
    handler = RecordingHandler(results={"before_serialize": (False, {"replaced": True})})
    c = _make_cache(handler)

    @c
    def echo(x):
        return {"value": x}

    stored = _captured_put_value(c, lambda: echo(1))

    # Caller always gets the original return value
    # (checked in test_write_path_returns_original_value)
    assert json.loads(stored) == {"replaced": True}
    c.policy.purge(redis_client=c.get_redis_client())


def test_before_serialize_handled_true_skips_serialization():
    """handled=True: value is bytes written directly, library serialization skipped."""
    raw = b"direct-bytes-payload"
    handler = RecordingHandler(results={"before_serialize": (True, raw)})
    c = _make_cache(handler)

    @c
    def echo(x):
        return {"value": x}

    stored = _captured_put_value(c, lambda: echo(1))
    assert stored == raw
    c.policy.purge(redis_client=c.get_redis_client())


def test_after_serialize_replaces_bytes():
    """after_serialize return value unconditionally replaces stored bytes."""
    raw = b"replaced-by-after-serialize"
    handler = RecordingHandler(results={"after_serialize": raw})
    c = _make_cache(handler)

    @c
    def echo(x):
        return {"value": x}

    stored = _captured_put_value(c, lambda: echo(1))
    assert stored == raw
    c.policy.purge(redis_client=c.get_redis_client())


def test_before_deserialize_handled_true_returns_final_value():
    """handled=True: value is final; deserialize and after_deserialize are skipped."""
    handler = RecordingHandler(results={"before_deserialize": (True, {"final": True})})
    c = _make_cache(handler)

    @c
    def echo(x):
        return {"value": x}

    # First call: miss, write path runs (before_serialize returns (False, value))
    assert echo(1) == {"value": 1}

    # Second call: hit, before_deserialize handled=True
    result = echo(1)
    assert result == {"final": True}

    # after_deserialize must NOT have been called on the handled path
    deserialize_calls = [name for name, _ in handler.calls if name == "after_deserialize"]
    assert deserialize_calls == []
    c.policy.purge(redis_client=c.get_redis_client())


def test_before_deserialize_handled_false_replaces_bytes():
    """handled=False: returned value replaces cached bytes, then library deserializes."""
    handler = RecordingHandler(
        results={
            # First call (miss): store as normal
            "before_serialize": (False, {"value": 1}),
            # Second call (hit): rewrite bytes before deserialize
            "before_deserialize": (False, json.dumps({"value": 42}).encode()),
        }
    )
    c = _make_cache(handler)

    @c
    def echo(x):
        return {"value": x}

    assert echo(1) == {"value": 1}  # miss → write
    assert echo(1) == {"value": 42}  # hit → bytes replaced → deserialized to 42
    c.policy.purge(redis_client=c.get_redis_client())


def test_after_deserialize_replaces_result():
    """after_deserialize return value unconditionally replaces the result on hit."""
    handler = RecordingHandler(results={"after_deserialize": {"decorated": True}})
    c = _make_cache(handler)

    @c
    def echo(x):
        return {"value": x}

    # Miss → write
    assert echo(1) == {"value": 1}
    # Hit → after_deserialize replaces
    assert echo(1) == {"decorated": True}
    c.policy.purge(redis_client=c.get_redis_client())


def test_write_path_returns_original_value():
    """Handler affects storage, not the value returned to the caller."""
    handler = RecordingHandler(
        results={
            "before_serialize": (True, b"stored-bytes"),
            "after_serialize": b"stored-bytes-2",
        }
    )
    c = _make_cache(handler)

    @c
    def echo(x):
        return {"original": x}

    assert echo(7) == {"original": 7}
    c.policy.purge(redis_client=c.get_redis_client())


def test_handler_subset_only_before_serialize():
    """A handler may implement only one method."""

    class OnlyBeforeSerialize:
        def __init__(self):
            self.calls = []

        def before_serialize(self, value, **kwargs):
            self.calls.append(value)
            return True, b"only-before-serialize"

    c = _make_cache(OnlyBeforeSerialize())

    @c
    def echo(x):
        return {"value": x}

    stored = _captured_put_value(c, lambda: echo(1))
    assert stored == b"only-before-serialize"
    c.policy.purge(redis_client=c.get_redis_client())


def test_mode_write_false_skips_write_handler():
    """When writing is disabled, serialize handlers are never called."""
    handler = RecordingHandler()
    c = _make_cache(handler)

    @c
    def echo(x):
        return {"value": x}

    mode = c.get_mode()
    mode.write = False
    mode.exec = True
    with c.mode_context(mode):
        # read=True, miss → exec allowed, write skipped
        assert echo(1) == {"value": 1}

    assert "before_serialize" not in [name for name, _ in handler.calls]
    assert "after_serialize" not in [name for name, _ in handler.calls]
    c.policy.purge(redis_client=c.get_redis_client())


def test_mode_read_false_skips_read_handler():
    """When reading is disabled, deserialize handlers are never called."""
    handler = RecordingHandler()
    c = _make_cache(handler)

    @c
    def echo(x):
        return {"value": x}

    # Prime the cache
    assert echo(1) == {"value": 1}
    handler.calls.clear()

    mode = c.get_mode()
    mode.read = False
    with c.mode_context(mode):
        assert echo(1) == {"value": 1}

    assert "before_deserialize" not in [name for name, _ in handler.calls]
    assert "after_deserialize" not in [name for name, _ in handler.calls]
    c.policy.purge(redis_client=c.get_redis_client())


def test_validation_sync_method_must_not_be_coroutine():
    """A sync-named method that is a coroutine function raises at registration."""

    class BadHandler:
        async def before_serialize(self, value, **kwargs):
            return False, value

    with pytest.raises(TypeError, match="before_serialize must not be a coroutine"):
        _make_cache(BadHandler())


def test_validation_async_method_must_be_coroutine():
    """An *_async method that is not a coroutine function raises at registration."""

    class BadHandler:
        def before_serialize_async(self, value, **kwargs):
            return False, value

    with pytest.raises(TypeError, match="before_serialize_async must be a coroutine"):
        _make_cache(BadHandler())


def test_handler_protocol_exported():
    assert HandlerProtocol is not None
    from redis_func_cache import HandlerProtocol as HP

    assert HP is HandlerProtocol


@pytest.mark.asyncio(loop_scope="function")
async def test_async_handler_full_cycle(async_cache: RedisFuncCache):
    """Async handler with all four async methods works end to end.

    Write path: before_serialize handled=True stores raw bytes directly.
    Read path: before_deserialize handled=True returns the final value,
    skipping library deserialize and after_deserialize.
    """
    handler = AsyncRecordingHandler(
        results={
            "before_serialize": (True, b"async-stored"),
            "before_deserialize": (True, {"resolved": True}),
        }
    )
    c = _make_async_cache(handler)

    @c
    async def echo(x):
        await asyncio.sleep(0)
        return {"value": x}

    # Miss → write path (before_serialize handled=True stores b"async-stored")
    assert await echo(1) == {"value": 1}

    # Hit → before_deserialize handled=True returns final value
    assert await echo(1) == {"resolved": True}

    names = [name for name, _ in handler.calls]
    assert "before_serialize" in names
    assert "after_serialize" in names
    assert "before_deserialize" in names
    # after_deserialize is skipped when before_deserialize is handled
    assert "after_deserialize" not in names
    await c.policy.apurge(redis_client=c.get_redis_client())


@pytest.mark.asyncio(loop_scope="function")
async def test_async_before_deserialize_handled_true(async_cache: RedisFuncCache):
    """Async before_deserialize handled=True returns final value, skips after_deserialize."""
    handler = AsyncRecordingHandler(results={"before_deserialize": (True, {"final": True})})
    c = _make_async_cache(handler)

    @c
    async def echo(x):
        await asyncio.sleep(0)
        return {"value": x}

    assert await echo(1) == {"value": 1}
    assert await echo(1) == {"final": True}

    assert "after_deserialize" not in [name for name, _ in handler.calls]
    await c.policy.apurge(redis_client=c.get_redis_client())


@pytest.mark.asyncio(loop_scope="function")
async def test_async_falls_back_to_sync_methods(async_cache: RedisFuncCache):
    """A sync-only handler works with the async execution path via fallback."""
    handler = RecordingHandler(results={"after_deserialize": {"from_sync_fallback": True}})
    c = _make_async_cache(handler)

    @c
    async def echo(x):
        await asyncio.sleep(0)
        return {"value": x}

    assert await echo(1) == {"value": 1}
    assert await echo(1) == {"from_sync_fallback": True}

    names = [name for name, _ in handler.calls]
    assert "before_serialize" in names
    assert "after_deserialize" in names
    await c.policy.apurge(redis_client=c.get_redis_client())


@pytest.mark.asyncio(loop_scope="function")
async def test_async_after_deserialize_returns_value_not_tuple(async_cache: RedisFuncCache):
    """Regression: async after_deserialize must return the value, not (handled, value)."""
    handler = AsyncRecordingHandler(results={"after_deserialize": "just-a-string"})
    c = _make_async_cache(handler)

    @c
    async def echo(x):
        await asyncio.sleep(0)
        return {"value": x}

    assert await echo(1) == {"value": 1}
    result = await echo(1)
    assert result == "just-a-string"
    assert not isinstance(result, tuple)
    await c.policy.apurge(redis_client=c.get_redis_client())


@pytest.mark.asyncio(loop_scope="function")
async def test_async_after_serialize_returns_bytes_not_tuple(async_cache: RedisFuncCache):
    """Regression: async after_serialize must return bytes, not (handled, bytes)."""
    handler = AsyncRecordingHandler(results={"after_serialize": b"raw-bytes"})
    c = _make_async_cache(handler)

    @c
    async def echo(x):
        await asyncio.sleep(0)
        return {"value": x}

    with patch.object(c, "aput") as mock_aput:
        await echo(1)
        mock_aput.assert_called_once()
        stored = mock_aput.call_args[0][3]

    assert stored == b"raw-bytes"
    await c.policy.apurge(redis_client=c.get_redis_client())


def test_handler_context_kwargs_passed():
    """Handler receives keys, hash_value, func, args, kwds keyword arguments."""
    seen: dict[str, Any] = {}

    class ContextHandler:
        def before_serialize(self, value, **kwargs):
            seen.update(kwargs)
            return False, value

    c = _make_cache(ContextHandler())

    def add(a, b):
        return a + b

    decorated = c(add)
    assert decorated(1, 2) == 3
    assert "keys" in seen
    assert "hash_value" in seen
    assert seen["args"] == (1, 2)
    assert seen["kwds"] == {}
    c.policy.purge(redis_client=c.get_redis_client())


def test_before_deserialize_not_called_on_miss():
    """Deserialize handlers only run on cache hits."""
    handler = RecordingHandler()
    c = _make_cache(handler)

    @c
    def echo(x):
        return {"value": x}

    assert echo(1) == {"value": 1}  # miss
    assert "before_deserialize" not in [name for name, _ in handler.calls]
    assert "after_deserialize" not in [name for name, _ in handler.calls]

    assert echo(1) == {"value": 1}  # hit
    assert "before_deserialize" in [name for name, _ in handler.calls]
    assert "after_deserialize" in [name for name, _ in handler.calls]
    c.policy.purge(redis_client=c.get_redis_client())
