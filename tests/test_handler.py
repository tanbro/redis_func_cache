"""Tests for the handler system (four serialization boundaries)."""

from __future__ import annotations

import asyncio
import json
from dataclasses import FrozenInstanceError
from typing import Any
from unittest.mock import patch

import pytest
import pytest_asyncio

from redis_func_cache import HandlerContext, HandlerProtocol, LruPolicy, RedisFuncCache

from ._catches import ASYNC_REDIS_FACTORY, REDIS_FACTORY


class RecordingHandler:
    """A handler that records every call and returns configurable results."""

    def __init__(self, results: dict[str, Any] | None = None):
        self.calls: list[tuple[str, Any]] = []
        self.contexts: list[HandlerContext] = []
        self.results = results or {}

    def _result(self, name: str, default: Any) -> Any:
        if name in self.results:
            return self.results[name]
        return default

    def before_serialize(self, value, *, ctx):
        self.calls.append(("before_serialize", value))
        self.contexts.append(ctx)
        return self._result("before_serialize", (False, value))

    def after_serialize(self, value, *, ctx):
        self.calls.append(("after_serialize", value))
        self.contexts.append(ctx)
        return self._result("after_serialize", value)

    def before_deserialize(self, value, *, ctx):
        self.calls.append(("before_deserialize", value))
        self.contexts.append(ctx)
        return self._result("before_deserialize", (False, value))

    def after_deserialize(self, value, *, ctx):
        self.calls.append(("after_deserialize", value))
        self.contexts.append(ctx)
        return self._result("after_deserialize", value)


class AsyncRecordingHandler:
    """Async variant of :class:`RecordingHandler`."""

    def __init__(self, results: dict[str, Any] | None = None):
        self.calls: list[tuple[str, Any]] = []
        self.contexts: list[HandlerContext] = []
        self.results = results or {}

    def _result(self, name: str, default: Any) -> Any:
        if name in self.results:
            return self.results[name]
        return default

    async def before_serialize_async(self, value, *, ctx):
        self.calls.append(("before_serialize", value))
        self.contexts.append(ctx)
        return self._result("before_serialize", (False, value))

    async def after_serialize_async(self, value, *, ctx):
        self.calls.append(("after_serialize", value))
        self.contexts.append(ctx)
        return self._result("after_serialize", value)

    async def before_deserialize_async(self, value, *, ctx):
        self.calls.append(("before_deserialize", value))
        self.contexts.append(ctx)
        return self._result("before_deserialize", (False, value))

    async def after_deserialize_async(self, value, *, ctx):
        self.calls.append(("after_deserialize", value))
        self.contexts.append(ctx)
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


def test_before_serialize_handled_true_skips_serialization_and_after():
    """handled=True: value is bytes written directly; serialization and after_serialize are skipped."""
    raw = b"direct-bytes-payload"
    handler = RecordingHandler(results={"before_serialize": (True, raw)})
    c = _make_cache(handler)

    @c
    def echo(x):
        return {"value": x}

    stored = _captured_put_value(c, lambda: echo(1))
    assert stored == raw
    # Symmetric short-circuit: after_serialize must not run when before handled
    assert "after_serialize" not in [name for name, _ in handler.calls]
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
        }
    )
    c = _make_cache(handler)

    @c
    def echo(x):
        return {"original": x}

    assert echo(7) == {"original": 7}
    c.policy.purge(redis_client=c.get_redis_client())


def test_handler_subset_only_before_serialize():
    """A handler may define only the methods its usage actually reaches.

    Per the contract, every method of the implemented group is defined —
    identity returns for boundaries the handler does not use. This test
    pins a narrower handler that defines only ``before_serialize``: it
    works here because ``handled=True`` short-circuits
    ``after_serialize`` and only the write path ever runs.
    """

    class OnlyBeforeSerialize:
        def __init__(self):
            self.calls = []

        def before_serialize(self, value, *, ctx):
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


def test_handler_protocol_exported():
    assert HandlerProtocol is not None
    from redis_func_cache import HandlerContext as HC
    from redis_func_cache import HandlerProtocol as HP

    assert HP is HandlerProtocol
    assert HC is HandlerContext


def test_handler_context_is_frozen():
    """HandlerContext is immutable."""
    ctx = HandlerContext(keys=("k0", "k1"), hash_value="h", func=None)
    with pytest.raises(FrozenInstanceError):
        ctx.hash_value = "other"


def test_before_serialize_bad_shape_propagates():
    """A malformed before-boundary return value surfaces the natural unpack error (no library validation)."""
    handler = RecordingHandler(results={"before_serialize": "not-a-tuple"})
    c = _make_cache(handler)

    @c
    def echo(x):
        return {"value": x}

    with pytest.raises((TypeError, ValueError), match="unpack"):
        echo(1)
    c.policy.purge(redis_client=c.get_redis_client())


@pytest.mark.asyncio(loop_scope="function")
async def test_async_handler_full_cycle(async_cache: RedisFuncCache):
    """Async handler with all four async methods works end to end.

    Write path: before_serialize handled=True stores raw bytes directly and
    skips after_serialize. Read path: before_deserialize handled=True returns
    the final value, skipping library deserialize and after_deserialize.
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

    names = [name for name, _ in handler.calls]
    assert "before_serialize" in names
    # Symmetric short-circuit: after_serialize is skipped on the handled path
    assert "after_serialize" not in names

    # Hit → before_deserialize handled=True returns final value
    assert await echo(1) == {"resolved": True}

    names = [name for name, _ in handler.calls]
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
async def test_async_unsupported_boundary_raises_not_implemented(async_cache: RedisFuncCache):
    """A handler raising NotImplementedError propagates unchanged — no library error handling for handler failures."""

    class PartialAsyncHandler:
        async def before_serialize_async(self, value, *, ctx):
            raise NotImplementedError

    c = _make_async_cache(PartialAsyncHandler())

    @c
    async def echo(x):
        await asyncio.sleep(0)
        return {"value": x}

    with pytest.raises(NotImplementedError):
        await echo(1)
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


@pytest.mark.asyncio(loop_scope="function")
async def test_async_before_serialize_bad_shape_propagates(async_cache: RedisFuncCache):
    """A malformed async before-boundary return value surfaces the natural unpack error."""
    handler = AsyncRecordingHandler(results={"before_serialize": 42})
    c = _make_async_cache(handler)

    @c
    async def echo(x):
        await asyncio.sleep(0)
        return {"value": x}

    with pytest.raises(TypeError, match="not unpackable|unpack"):
        await echo(1)
    await c.policy.apurge(redis_client=c.get_redis_client())


def test_handler_context_passed():
    """Handler receives a HandlerContext with keys, hash_value, func, args, kwds."""
    handler = RecordingHandler()
    c = _make_cache(handler)

    def add(a, b):
        return a + b

    decorated = c(add)
    assert decorated(1, 2) == 3

    ctx = handler.contexts[0]
    assert isinstance(ctx, HandlerContext)
    assert isinstance(ctx.keys, tuple) and len(ctx.keys) == 2
    assert ctx.func is add
    assert ctx.args == (1, 2)
    assert ctx.kwds == {}
    c.policy.purge(redis_client=c.get_redis_client())


def test_handler_context_uses_bound_args_matching_key_computation():
    """ctx.args/ctx.kwds are the excludes-filtered arguments, consistent with key calculation."""
    handler = RecordingHandler()
    c = _make_cache(handler)

    def raw_call(user_id, token=None):
        return user_id

    decorated = c.decorate(excludes=["token"])(raw_call)
    assert decorated(7, token="secret") == 7

    ctx = handler.contexts[0]
    assert ctx.args == (7,)
    assert ctx.kwds == {}

    # The same filtered args drive key computation: same effective args → same keys/hash
    assert ctx.func is raw_call
    assert ctx.keys == c.policy.calc_keys(raw_call, (7,), {})
    assert ctx.hash_value == c.policy.calc_hash(raw_call, (7,), {})
    c.policy.purge(redis_client=c.get_redis_client())


def test_per_function_handler_overrides_instance_handler():
    """A decorate-level handler replaces the instance-level handler."""
    instance_handler = RecordingHandler(results={"after_serialize": b"instance-bytes"})
    func_handler = RecordingHandler(results={"after_serialize": b"func-bytes"})
    c = _make_cache(instance_handler)

    @c.decorate(handler=func_handler)
    def echo(x):
        return {"value": x}

    stored = _captured_put_value(c, lambda: echo(1))
    assert stored == b"func-bytes"
    assert instance_handler.calls == []
    c.policy.purge(redis_client=c.get_redis_client())


def test_per_function_handler_defaults_to_instance_handler():
    """Without a decorate-level handler, the instance-level handler is used."""
    instance_handler = RecordingHandler(results={"after_serialize": b"instance-bytes"})
    c = _make_cache(instance_handler)

    @c.decorate()
    def echo(x):
        return {"value": x}

    stored = _captured_put_value(c, lambda: echo(1))
    assert stored == b"instance-bytes"
    assert instance_handler.calls
    c.policy.purge(redis_client=c.get_redis_client())


def test_before_deserialize_not_called_on_miss():
    """Deserialize handlers only run on cache hits."""
    handler = RecordingHandler()
    c = _make_cache(handler)

    @c
    def echo(x):
        return {"value": 1}

    assert echo(1) == {"value": 1}  # miss
    assert "before_deserialize" not in [name for name, _ in handler.calls]
    assert "after_deserialize" not in [name for name, _ in handler.calls]

    assert echo(1) == {"value": 1}  # hit
    assert "before_deserialize" in [name for name, _ in handler.calls]
    assert "after_deserialize" in [name for name, _ in handler.calls]
    c.policy.purge(redis_client=c.get_redis_client())
