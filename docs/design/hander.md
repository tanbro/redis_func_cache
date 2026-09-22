---
status: draft
create_at: 2026-09-22
---

# Proposal: Handler System for `redis_func_cache`

## Summary

Introduce a single, optional **handler** that wraps the four serialization boundaries of the cache: before serialize, after serialize, before deserialize, after deserialize.

The driving use case is **offloading large values to object storage**: Redis stores only a small reference; the application resolves it back on read. The library never learns about the object store.

A handler is an active extension point, not a passive callback: when it reports that it has handled a boundary, the library skips its own step at that boundary and uses the handler's value.

## Motivation

The existing extension point is the `serializer` argument — a pair of plain functions `(serialize, deserialize)`. Three properties of that API block the offload use case:

1. **Synchronous only.** A serializer must return immediately. Writing to or reading from object storage is I/O; doing it synchronously blocks the caller or the event loop.
2. **No call context.** A serializer receives only the value. It cannot see the cache keys, hash field, decorated function, or invocation arguments — all of which an offload handler typically needs to build a storage key or path.
3. **All-or-nothing override.** Providing a custom serializer replaces both directions. There is no way to override only the write path (or only the read path) while keeping the library's default encoding on the other side.

A handler addresses all three: it supports async methods, receives keyword-only context, and each of the four boundaries is independently optional — an unimplemented boundary falls through to the library default.

### Concrete use case

An application caches the result of a function that returns a multi-megabyte HTML page.

Caching the page directly in Redis is an abuse: it consumes Redis memory, blocks the single-threaded event loop on large reads and writes, and slows replication. The desired design is a two-tier cache. Redis stores only a small reference plus metadata; object storage stores the actual payload. The library manages the Redis side — key computation, eviction policy, TTL, concurrency control — and knows nothing about object storage.

On the write path the handler replaces the large value with a small reference. On the read path it resolves the reference back to the value and takes over deserialization.

## Design Goals

1. Backward compatible. With no handler configured, behavior is identical to today.
2. Single handler. Exactly one handler per cache instance. No chains, no ordering rules, no composition inside the library.
3. Symmetric. Handlers exist on both the write path and the read path.
4. Async aware. Handlers work for both synchronous and asynchronous decorated functions, via paired sync and `*_async` methods.
5. Non-invasive. The core cache logic — key calculation, Lua scripts, eviction — is unchanged; the serializer hot path is untouched.
6. Optional methods. A handler may implement any subset of the boundaries; missing methods fall through to the library default.

## Non-Goals

1. Built-in object storage support. The library must not depend on any specific object store.
2. Multiple handlers. Composition, if needed, is the application's responsibility.
3. A general middleware framework. Handlers are scoped to the four serialization boundaries only.
4. Changes to the eviction algorithm or Redis data structures.
5. Per-value write suppression. A handler can change *what* is written but cannot prevent the write. Skipping the write for a particular result is the caller's job (cache mode, or not calling the cached function path).
6. Failure policy. The library does not retry, degrade, or fall back on handler errors — see Error Handling below. Reliability policy belongs to the application.

## When to Use a Handler vs a Serializer

| | `serializer=(ser, des)` | `handler=` |
|---|---|---|
| Encoding format only (JSON, msgpack, …) | ✅ preferred | overkill |
| Sync custom encoding | ✅ preferred | overkill |
| Async I/O (object storage, remote fetch) | ❌ sync only | ✅ |
| Needs keys / args / func context | ❌ value only | ✅ |
| Override one direction, keep library default on the other | ❌ both required | ✅ per-boundary optional |
| Post-process deserialized value (enrichment, validation) | possible inside `des` | ✅ clearer at `after_deserialize` |
| Compress/encrypt library-produced bytes | ❌ | ✅ at `after_serialize` |

Rule of thumb: if you are only choosing an encoding, use `serializer`. If you need async I/O, call context, or partial override of the library's own steps, use `handler`. The two may be combined: `serializer` defines the default encoding; `handler` may replace bytes at any boundary.

## The Handler Methods

The handler interface defines up to eight methods: four boundaries, each with a sync and an async variant. Every method is optional.

| Boundary | Sync method | Async method |
|---|---|---|
| Write, before library serializes | `before_serialize` | `before_serialize_async` |
| Write, after library serializes | `after_serialize` | `after_serialize_async` |
| Read, before library deserializes | `before_deserialize` | `before_deserialize_async` |
| Read, after library deserializes | `after_deserialize` | `after_deserialize_async` |

Each method receives the value being processed as its first positional argument, plus keyword-only context:

- `keys`: the `(zset_key, hash_key)` pair for this cache entry.
- `hash_value`: the hash field for this invocation.
- `func`, `args`, `kwds`: the decorated function and its invocation arguments.

## Return Conventions

There are two conventions, one per category of boundary.

### Before boundaries return `(handled, value)`

`before_serialize` and `before_deserialize` (and `*_async`) return `(handled, value)`.

- `value` **always** replaces the working value for this path, regardless of `handled`. When the method is implemented, the library never falls back to the original input.
- `handled` controls whether the library still performs its own default operation:

**before_serialize**

- `handled=True`: the library **skips** its serializer. `value` must already be encoded bytes (or a str acceptable to Redis) and is written to Redis as-is.
- `handled=False`: the library serializes `value` with its configured serializer (or the `serialize_func` override from `decorate`).

**before_deserialize**

- `handled=True`: `value` is the **final** result returned to the caller. The library skips its deserializer and does **not** call `after_deserialize`.
- `handled=False`: `value` replaces the bytes read from Redis; the library deserializes `value`.

### After boundaries return the replacement value directly

`after_serialize` and `after_deserialize` (and `*_async`) return the replacement value — **not** a tuple. After these boundaries there is no default library step left for the handler to skip, so a `handled` flag would carry no information; the return value unconditionally wins.

- `after_serialize`: replaces the bytes about to be written to Redis (compression, encryption, prefixes).
- `after_deserialize`: replaces the deserialized result (enrichment, validation, type conversion).

When an after-boundary method is not implemented, the library uses its own value unchanged.

## Read Path and Write Path

### Write path

Runs only when the mode allows writing:

1. The user function executes and returns a value.
2. The library calls `before_serialize` with the return value.
3. The returned `value` replaces the value to store. If `handled` is True, the library skips serialization and uses `value` as the stored bytes; otherwise it serializes `value`.
4. The library calls `after_serialize` with the bytes from step 3; the return value replaces them.
5. The library writes the bytes to Redis.

The value returned to the caller is always the original return value of the user function. The handler affects what is stored, not what is returned.

Unimplemented `before_serialize` degenerates to "serialize the original return value"; unimplemented `after_serialize` skips step 4.

### Read path

Runs only when the mode allows reading:

1. The library reads bytes from Redis.
2. No bytes → cache miss.
3. The library calls `before_deserialize` with the bytes.
4. The returned `value` replaces the working bytes. If `handled` is True, `value` is the final result: skip steps 5–6 and return it. If `handled` is False, deserialize `value`.
5. The library deserializes (when `handled` was False).
6. The library calls `after_deserialize` with the deserialized value; the return value replaces it.
7. The result is returned to the caller.

Unimplemented `before_deserialize` degenerates to "deserialize the bytes read from Redis"; unimplemented `after_deserialize` skips step 6.

## Interaction with Cache Mode

1. When reading is disabled, `before_deserialize` and `after_deserialize` are never called.
2. When writing is disabled, `before_serialize` and `after_serialize` are never called.
3. When both are disabled, no handler method is called.

This preserves the existing write-only, read-only, and disabled mode semantics.

## Error Handling

Handlers are orthogonal to `ignore_redis_errors`:

1. Redis errors from the library's own get/put are handled by the existing logic and are not routed through the handler.
2. Exceptions raised by the handler propagate to the caller. **The library provides no retry, fallback, or degradation policy** (Non-Goal 6); the handler is responsible for its own error handling.
3. A handler may catch its own exceptions and return `handled=False` (before-boundaries) or the original value (after-boundaries) to fall back to the library default.

## Sync and Async Methods

The interface uses **paired method names** rather than runtime coroutine detection:

1. The synchronous path calls the non-`_async` methods. These **must not** be coroutine functions; the library calls them without awaiting. Violations raise `TypeError` at construction.
2. The asynchronous path prefers the `*_async` methods, which **must** be coroutine functions; the library awaits them. Violations raise `TypeError` at construction.
3. When an `*_async` method is absent, the asynchronous path **falls back** to the synchronous method of the same boundary, awaiting the result if it is awaitable. A sync-only handler therefore works with both sync and async caches.
4. A handler may mix sync and async methods freely across boundaries.

## Validation

At cache construction time:

1. An implemented sync-named method that is a coroutine function → `TypeError`.
2. An implemented `*_async` method that is not a coroutine function → `TypeError`.
3. A handler with no methods at all is allowed (a no-op).

## Registration

A handler is provided at construction time via the optional `handler` argument. With no handler, behavior is identical to the current implementation.

A cache instance holds at most one handler; there is no way to add a second after construction. This keeps semantics simple and unambiguous.

`HandlerProtocol` is exported from the package root:

```python
from redis_func_cache import HandlerProtocol, RedisFuncCache
```

## Example: Object Storage Offload

Implement two methods: `before_serialize` and `before_deserialize`.

**Write** — in `before_serialize`: if the value is small, return `(False, value)` and the library stores it in Redis as usual. If it is large, upload the payload to object storage, build a small encoded reference (bytes), and return `(True, reference_bytes)`. The library skips its serializer and stores only the reference.

**Read** — in `before_deserialize`: if the bytes are a normal small value, return `(False, bytes)` and the library deserializes as usual. If they are a reference, fetch the payload from object storage, parse it, and return `(True, final_value)`. The library skips its deserializer and `after_deserialize`, and returns the value directly.

Only the two `before_*` methods are needed; `after_*` are unimplemented and fall through. The library remains unaware of object storage — it sees a small value on write and a final value on read.

## Backward Compatibility

1. With no handler, the code path is exactly as before.
2. Existing serializer arguments work unchanged. A handler and a serializer may be combined: the serializer defines the default encoding for `handled=False`; the handler may replace bytes at any boundary.
3. The handler system is additive; it replaces and deprecates nothing.

## Alternatives Considered

### Extending the serializer to async callables

Rejected. Making `serializer` accept async callables would force the core `serialize()` hot path to branch on coroutine-ness and await — an invasive change to the hottest code in the library — and a serializer pair still cannot expose call context or allow overriding only one direction while keeping the library default on the other. The handler keeps the serializer path untouched and covers all three motivation points.

### Multiple hooks with a chain

Rejected. Ordering rules, composition semantics, and ambiguity when two hooks want the same boundary. Composition is the application's responsibility.

### A sentinel value to signal bypass

Rejected. `before_deserialize`'s normal path already must return a value, which conflicts with a "no value" sentinel. `handled` avoids the conflict on before-boundaries; after-boundaries have no default step to bypass and need no flag.

### Raising a special exception to signal bypass

Rejected. Exceptions for control flow complicate testing and do not extend naturally to the other boundaries.

### A mutable context object shared across boundaries

Rejected for now. New concept, shared mutable state. Keyword-only context (`keys`, `hash_value`, `func`, `args`, `kwds`) covers known needs; a context object can be added later additively if a real need arises.

### A middleware chain

Rejected. Target use cases are transformations at specific boundaries, not wrapping the execution flow. A middleware chain would restructure the core path and introduce a second extension model alongside policy and serializer.

### Runtime coroutine detection on a single set of method names

Rejected in favor of paired `*_async` names. Runtime detection branches on every call, makes registration-time validation impossible, and obscures whether a handler is safe from a synchronous context. Paired names make the contract explicit and checkable at construction.

## Open Questions

1. Should the protocol be a runtime-checkable Protocol, an ABC, or plain duck typing. *(Current: non-runtime-checkable Protocol for static typing; duck-typed at runtime.)*
2. Should the library ship a no-op base handler for selective subclassing.
3. Should registration require at least one method.

## Implementation Plan

1. Define the handler protocol with four boundaries, sync/async pairs, and the two return conventions. *(Done: `HandlerProtocol` in `hook.py`.)*
2. Optional `handler` argument on the cache constructor. *(Done.)*
3. Validate sync/async method shapes at construction. *(Done: `validate_handler`.)*
4. Insert handler calls at the four boundaries in both execution paths, with optional-method checks and async-to-sync fallback. *(Done: `invoke_*` / `ainvoke_*` in `hook.py`.)*
5. Respect cache mode. *(Done: handlers only run inside `mode.read` / `mode.write`.)*
6. Tests: no handler, full handler, subsets, sync/async, `handled` True/False per boundary, async fallback, validation errors, mode interaction. *(Done: `tests/test_handler.py`.)*
7. Document the handler system and offload use case in the README. *(Done.)*
8. Export `HandlerProtocol` from the package root. *(Done.)*

## References

1. Existing serializer API: the `serializer` argument of the cache constructor.
2. Existing sync/async split documented in the README.
3. Related design note: caching large values in Redis is an anti-pattern.
4. Implementation: `src/redis_func_cache/hook.py` (`HandlerProtocol`, `validate_handler`, `invoke_*`, `ainvoke_*`), `src/redis_func_cache/cache.py` (call sites in `exec` / `aexec`).
5. Tests: `tests/test_handler.py`.
