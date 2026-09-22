---
status: draft
create_at: 2026-09-22
---

# Proposal: Handler System for `redis_func_cache`

## Summary

Introduce a single, optional **handler** that wraps the four serialization boundaries of the cache: before serialize, after serialize, before deserialize, after deserialize.

A handler lets application code take over any of these boundaries. It is not a passive callback. When a handler reports that it has handled a boundary, the library stops doing its own work at that boundary and uses the value the handler returned instead.

The goal is to keep `redis_func_cache` a pure function-level cache primitive while giving applications a clean extension point for concerns that are out of scope for the library itself, such as storing large values outside Redis and caching only a small reference.

## Motivation

### Current limitation

The current extension point is the serializer argument, which accepts a pair of plain functions: one for serialization and one for deserialization. This is too low-level for several real use cases:

1. It is synchronous only. A serializer must return immediately. Any I/O, such as writing to object storage, blocks the caller or the event loop.
2. There is no place to run logic before serialization or after deserialization.
3. There is no defined way to bypass the library's own serialize or deserialize step when the cached bytes are not in the format the library expects.
4. There is no failure strategy. If serialization or an external store fails, the library can only propagate the exception.

### Concrete use case

An application caches the result of a function that returns a multi-megabyte HTML page.

Caching the page directly in Redis is an abuse. It consumes Redis memory, blocks the single-threaded event loop on large reads and writes, and slows replication. The desired design is a two-tier cache. Redis stores only a small reference plus metadata. Object storage stores the actual payload. The library should manage the Redis side, including key computation, eviction policy, TTL, and concurrency control, without knowing anything about object storage.

A handler provides exactly the extension point needed. On the write path, the application replaces the large value with a small reference. On the read path, the application resolves the reference back to the value and takes over the deserialization step.

## Design Goals

1. Backward compatible. With no handler configured, behavior is identical to today.
2. Single handler. There is exactly one handler per cache instance. No chains, no ordering rules, no composition inside the library.
3. Symmetric. Handlers exist on both the write path and the read path.
4. Async aware. Handlers work for both synchronous and asynchronous decorated functions, via paired sync and `*_async` methods.
5. Non-invasive. The core cache logic, including key calculation, Lua scripts, and eviction, is unchanged.
6. Optional methods. A handler may implement any subset of the boundaries.

## Non-Goals

1. Built-in object storage support. The library must not depend on any specific object store.
2. Multiple handlers. Composition, if needed, is the application's responsibility.
3. A general middleware framework. Handlers are scoped to the four serialization boundaries only.
4. Changes to the eviction algorithm or Redis data structures.

## The Handler Methods

The handler interface defines up to eight methods, organized as four boundaries with a sync and an async variant each. Every method is optional; a handler may implement only the ones it needs.

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

There are two return conventions, one per category of boundary.

### Before boundaries return `(handled, value)`

`before_serialize` and `before_deserialize` (and their `*_async` variants) return a 2-tuple of `(handled, value)`.

- The `value` **always** replaces the working value for this path, regardless of `handled`. The library never falls back to the original input when a handler method is present and returns a value.
- `handled` controls whether the library performs its own default operation:

**before_serialize:**

- `handled=True`: the library **skips** its serializer. `value` must already be encoded bytes (or a str acceptable to Redis) and is written to Redis as-is.
- `handled=False`: the library serializes `value` with its configured serializer (or the `serialize_func` override from `decorate`).

**before_deserialize:**

- `handled=True`: `value` is the **final** result returned to the caller. The library skips its own deserializer and does **not** call `after_deserialize`.
- `handled=False`: `value` replaces the bytes read from Redis; the library proceeds to deserialize `value`.

### After boundaries return the replacement value directly

`after_serialize` and `after_deserialize` (and their `*_async` variants) return the replacement value directly — **not** a tuple. There is no default library step left after these boundaries for the handler to skip, so no `handled` flag is needed.

- `after_serialize`: the return value unconditionally replaces the bytes about to be written to Redis.
- `after_deserialize`: the return value unconditionally replaces the deserialized result returned to the caller.

When a handler does not implement an after-boundary method, the library uses its own value unchanged.

## Read Path and Write Path

### Write path

The write path runs only when the mode allows writing. The sequence is:

1. The user function is executed and returns a value.
2. The library calls `before_serialize` (or `before_serialize_async`) with the return value.
3. The returned `value` replaces the value to be stored. If `handled` is True, the library skips serialization and uses `value` as the stored bytes; otherwise the library serializes `value`.
4. The library calls `after_serialize` (or `after_serialize_async`) with the bytes from step 3. The return value replaces those bytes.
5. The library writes the bytes to Redis.

The value returned to the caller is always the original return value of the user function. The handler affects what is stored, not what is returned.

If `before_serialize` is not implemented, step 2–3 degenerate to "serialize the original return value". If `after_serialize` is not implemented, step 4 is skipped.

### Read path

The read path runs only when the mode allows reading. The sequence is:

1. The library reads bytes from Redis.
2. If no bytes are found, the library treats it as a cache miss.
3. The library calls `before_deserialize` (or `before_deserialize_async`) with the bytes.
4. The returned `value` replaces the working bytes. If `handled` is True, `value` is the final result: the library skips steps 5–6 and returns it. If `handled` is False, the library deserializes `value`.
5. The library deserializes (when `handled` was False).
6. The library calls `after_deserialize` (or `after_deserialize_async`) with the deserialized value. The return value replaces it.
7. The result is returned to the caller.

If `before_deserialize` is not implemented, step 3–4 degenerate to "deserialize the bytes read from Redis". If `after_deserialize` is not implemented, step 6 is skipped.

## Interaction with Cache Mode

The cache mode controls whether reading and writing are allowed. Handlers must respect the mode.

1. When reading is disabled, `before_deserialize` and `after_deserialize` are never called.
2. When writing is disabled, `before_serialize` and `after_serialize` are never called.
3. When both are disabled, no handler method is called.

This preserves the existing semantics of write only, read only, and disabled modes.

## Interaction with Redis Error Handling

The existing `ignore_redis_errors` option controls how Redis errors are handled. Handlers are orthogonal to this option.

1. Redis errors raised by the library's own get and put operations are handled by the existing logic and are not routed through the handler.
2. Exceptions raised by the handler itself are propagated to the caller. The handler is responsible for its own error handling.
3. A handler may choose to catch its own exceptions and return `handled` False (for before-boundaries) or the original value (for after-boundaries) to fall back to the library's default behavior.

## Sync and Async Methods

Handlers must work for both synchronous and asynchronous decorated functions.

The handler interface uses **paired method names** rather than runtime coroutine detection:

1. The synchronous execution path calls the non-`_async` methods (`before_serialize`, `after_serialize`, etc.). These **must not** be coroutine functions; the library calls them without awaiting. A violation raises `TypeError` at construction time.
2. The asynchronous execution path prefers the `*_async` methods (`before_serialize_async`, etc.), which **must** be coroutine functions; the library awaits them. A violation raises `TypeError` at construction time.
3. When an `*_async` method is absent, the asynchronous path **falls back** to the synchronous method of the same boundary, awaiting the result if it is awaitable. This lets a sync-only handler work with both sync and async caches.
4. A handler may implement any mix of sync and async methods across boundaries.

## Validation

The handler is validated at cache construction time:

1. Any implemented sync-named method that is a coroutine function raises `TypeError`.
2. Any implemented `*_async` method that is not a coroutine function raises `TypeError`.
3. A handler that implements no methods at all is allowed (it is a no-op), though of little use.

## Registration

A handler is provided at cache construction time via the optional `handler` argument. When it is not provided, behavior is identical to the current implementation.

A cache instance holds at most one handler. There is no method to add a second handler after construction. This is intentional, to keep the semantics simple and unambiguous.

`HandlerProtocol` is exported from the package root for typing purposes:

```python
from redis_func_cache import HandlerProtocol, RedisFuncCache
```

## Example Use Case: Object Storage Offload

This section describes how the handler system supports the object storage offload use case, without prescribing any specific storage backend.

A handler is implemented with two methods: `before_serialize` and `before_deserialize`.

In `before_serialize`, the handler inspects the value returned by the user function. If the value is small, the handler returns `(False, value)` and the library stores it in Redis as usual. If the value is large, the handler writes the payload to object storage, builds a small encoded reference (bytes), and returns `(True, reference_bytes)`. The library skips its serializer and stores only the small reference in Redis.

In `before_deserialize`, the handler inspects the bytes read from Redis. If the bytes represent a small value, the handler returns `(False, bytes)` and the library deserializes them as usual. If the bytes represent a reference, the handler fetches the payload from object storage, parses it, and returns `(True, final_value)`. The library skips its own deserialize step and `after_deserialize`, and returns the value directly.

The library remains unaware of object storage. It only sees a small value on the write path and a final value on the read path.

## Backward Compatibility

1. With no handler configured, the code path is exactly as before. The library serializes, writes, reads, and deserializes as it does today.
2. Existing serializer arguments continue to work unchanged. A handler and a serializer may be used together. The serializer defines the default encoding for the `handled=False` path, and the handler may replace bytes at any boundary.
3. The handler system is additive. It does not replace or deprecate any existing API.

## Alternatives Considered

### Extending the serializer to async callables

Rejected. It does not provide lifecycle points and conflates encoding with external I/O and failure handling.

### Multiple hooks with a chain

Rejected. It introduces ordering rules, composition semantics, and ambiguity when more than one hook wants to take over the same boundary. A single handler is sufficient for the target use cases, and composition can be implemented by the application if needed.

### A sentinel value to signal bypass

Rejected. The normal path of `before_deserialize` already needs to return a value, which conflicts with the use of a sentinel to mean "no value". A uniform `handled` boolean avoids this conflict for before-boundaries; after-boundaries do not need the flag at all.

### Raising a special exception to signal bypass

Rejected. It uses exceptions for control flow, complicates testing, and does not extend naturally to the other three boundaries.

### A mutable context object shared across boundaries

Rejected for now. It introduces a new concept and shared mutable state. Keyword-only context arguments (`keys`, `hash_value`, `func`, `args`, `kwds`) already cover the known needs. A context object may be added later as an additive extension if a real need arises.

### A middleware chain

Rejected. The target use cases are transformations at specific boundaries, not wrapping the entire execution flow. A middleware chain would require restructuring the core execution path and introduces a second extension model alongside the existing policy and serializer mechanisms.

### Runtime coroutine detection on a single set of method names

Rejected in favor of paired `*_async` names. Runtime detection requires the library to branch on every call, makes registration-time validation impossible, and obscures whether a handler is safe to call from a synchronous context. Paired names make the sync/async contract explicit and checkable at construction time.

## Open Questions

1. Should the handler protocol be a runtime-checkable Protocol, an abstract base class, or a plain duck-typed interface. *(Current: plain duck-typed with a non-runtime-checkable Protocol for static typing only.)*
2. Should the library provide a no-op base handler that applications can subclass and override selectively.
3. Should the library validate at registration time that the handler implements at least one method.

## Implementation Plan

1. Define the handler protocol with the four boundaries, sync/async method pairs, and the two return conventions. *(Done: `HandlerProtocol` in `hook.py`.)*
2. Add an optional handler argument to the cache constructor. *(Done.)*
3. Validate the handler at construction time, including the sync and async compatibility of its methods. *(Done: `validate_handler` in `hook.py`.)*
4. Insert handler calls into the existing synchronous and asynchronous execution paths at the four boundaries, with `hasattr` checks for optional methods and async-to-sync fallback. *(Done: `invoke_*` / `ainvoke_*` helpers in `hook.py`, called from `exec` / `aexec` in `cache.py`.)*
5. Respect the cache mode when deciding whether to call each handler method. *(Done: handlers are only invoked inside the `mode.read` / `mode.write` branches.)*
6. Add tests covering: no handler, handler with all methods, handler with a subset of methods, synchronous and asynchronous handlers, `handled` True and `handled` False at each boundary, async fallback, validation errors, and interaction with cache mode. *(Done: `tests/test_handler.py`.)*
7. Document the handler system and the object storage offload use case in the README. *(Pending.)*
8. Export `HandlerProtocol` from the package root. *(Done.)*

## References

1. Existing serializer API: the serializer argument of the cache constructor.
2. Existing sync and async split documented in the README.
3. Related design note: caching large values in Redis is an anti-pattern.
4. Implementation: `src/redis_func_cache/hook.py` (`HandlerProtocol`, `validate_handler`, `invoke_*`, `ainvoke_*`), `src/redis_func_cache/cache.py` (call sites in `exec` / `aexec`).
5. Tests: `tests/test_handler.py`.
