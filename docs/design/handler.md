---
status: accepted
create_at: 2026-09-22
updated_at: 2026-09-23
---

# Proposal: Handler System for `redis_func_cache`

## Summary

Introduce a single, optional **handler** that wraps the four serialization boundaries of the cache: before serialize, after serialize, before deserialize, after deserialize.

The driving use case is **offloading large values to object storage**: Redis stores only a small reference; the application resolves it back on read. The library never learns about the object store.

A handler is an active extension point, not a passive callback: when it reports that it has handled a boundary, the library skips **all** of its own remaining steps on that side, including the corresponding `after_*` method.

## Motivation

The existing extension point is the `serializer` argument — a pair of plain functions `(serialize, deserialize)`. Three properties of that API block the offload use case:

1. **Synchronous only.** A serializer must return immediately. Writing to or reading from object storage is I/O; doing it synchronously blocks the caller or the event loop.
2. **No call context.** A serializer receives only the value. It cannot see the cache keys, hash field, decorated function, or invocation arguments — all of which an offload handler typically needs to build a storage key or path.
3. **All-or-nothing override.** Providing a custom serializer replaces both directions. There is no way to override only the write path (or only the read path) while keeping the library's default encoding on the other side.

A handler addresses all three: it supports async methods, receives a call context, and each of the four boundaries is independently optional — an implementation simply does not support the boundaries it does not need.

### Concrete use case

An application caches the result of a function that returns a multi-megabyte HTML page.

Caching the page directly in Redis is an abuse: it consumes Redis memory, blocks the single-threaded event loop on large reads and writes, and slows replication. The desired design is a two-tier cache. Redis stores only a small reference plus metadata; object storage stores the actual payload. The library manages the Redis side — key computation, eviction policy, TTL, concurrency control — and knows nothing about object storage.

On the write path the handler replaces the large value with a small reference. On the read path it resolves the reference back to the value and takes over deserialization.

## Design Goals

1. Backward compatible. With no handler configured, behavior is identical to today.
2. Single handler. Exactly one handler per execution — the cache instance's handler, optionally overridden per decorated function. No chains, no ordering rules, no composition inside the library.
3. Symmetric. Handlers exist on both the write path and the read path, with one uniform short-circuit rule (see Return Conventions).
4. Async aware. Handlers work for both synchronous and asynchronous decorated functions, via paired sync and `*_async` methods. There is **no** async-to-sync fallback: the asynchronous path calls only `*_async` methods.
5. Non-invasive. The core cache logic — key calculation, Lua scripts, eviction — is unchanged; the serializer hot path is untouched.
6. Optional methods. `HandlerProtocol` is a pure structural protocol; an implementation decides which boundaries to support, and unsupported ones raise `NotImplementedError`.

## Non-Goals

1. Built-in object storage support. The library must not depend on any specific object store.
2. Multiple handlers. Composition, if needed, is the application's responsibility.
3. A general middleware framework. Handlers are scoped to the four serialization boundaries only.
4. Changes to the eviction algorithm or Redis data structures.
5. Per-value write suppression. A handler can change *what* is written but cannot prevent the write. Skipping the write for a particular result is the caller's job (cache mode, or not calling the cached function path).
6. Failure policy. The library does not retry, degrade, count, or fall back on handler errors — see Error Handling below. Reliability policy belongs entirely to the application.
7. Entry format versioning. Version or generation tags for handler-written bytes are the application's concern; the library offers no metadata channel for them.

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

The handler interface defines eight methods: four boundaries, each with a sync and an async variant.

`HandlerProtocol` is a **pure structural protocol** — signatures only, no implementation bodies, and implementations need not inherit from it (any class whose methods match the signatures is a valid handler). An implementation decides which boundaries to support, and whether to support them synchronously, asynchronously, or both; unsupported boundaries `raise NotImplementedError` — the standard file-like-object pattern. The execution paths call the methods **statically, one to one**, and what happens when an unsupported boundary is reached is entirely the implementation's business.

| Boundary | Sync method | Async method |
|---|---|---|
| Write, before library serializes | `before_serialize` | `before_serialize_async` |
| Write, after library serializes | `after_serialize` | `after_serialize_async` |
| Read, before library deserializes | `before_deserialize` | `before_deserialize_async` |
| Read, after library deserializes | `after_deserialize` | `after_deserialize_async` |

Each method receives the value being processed as its first positional argument, plus the immutable call context as a keyword-only parameter:

```python
def before_serialize(self, value, *, ctx: HandlerContext) -> tuple[bool, Any]: ...
```

### HandlerContext

```python
@dataclass(frozen=True)
class HandlerContext:
    keys: tuple[KeyT, KeyT]   # (zset_key, hash_key) for this cache entry
    hash_value: KeyT          # hash field for this invocation
    func: Callable | None     # the decorated function
    args: tuple               # effective positional arguments
    kwds: dict                # effective keyword arguments
```

`args` and `kwds` are the **effective** arguments — the same excludes-filtered arguments the library uses to compute `keys` and `hash_value`. A handler building a storage reference from them stays consistent with the cache key. The arguments the user function is called with remain the original, unfiltered ones.

A single frozen dataclass was chosen over flat keyword parameters so that future fields can be added without breaking existing handler implementations.

## Return Conventions

There are two conventions, one per category of boundary, plus one uniform short-circuit rule.

### Short-circuit rule

**`handled=True` means the handler owns everything after that boundary.** The library performs no further processing on that side — no serializer/deserializer, and no `after_*` method. The behavior table:

| | `handled=True` at before | after method runs? |
|---|---|---|
| Write path | value written as-is, serialization skipped | `after_serialize` **skipped** |
| Read path | value returned as final result, deserialization skipped | `after_deserialize` **skipped** |

The rationale: `after_*` methods post-process *library-produced* values. When a before-boundary is handled, no library-produced value exists; anything the handler wants layered on top, it composes itself inside the before method.

### Before boundaries return `(handled, value)`

`before_serialize` and `before_deserialize` (and `*_async`) return `(handled, value)`.

- `value` **always** replaces the working value for this path, regardless of `handled`. When the method is implemented, the library never falls back to the original input.
- `handled` controls whether the library still performs its own default operation:

**before_serialize**

- `handled=True`: the handler owns the rest of the write path. `value` must already be encoded bytes (or a str acceptable to Redis) and is written to Redis as-is; the library skips its serializer **and** `after_serialize`.
- `handled=False`: the library serializes `value` with its configured serializer (or the `serialize_func` override from `decorate`), then calls `after_serialize`.

**before_deserialize**

- `handled=True`: the handler owns the rest of the read path. `value` is the **final** result returned to the caller; the library skips its deserializer **and** `after_deserialize`.
- `handled=False`: `value` replaces the bytes read from Redis; the library deserializes `value`, then calls `after_deserialize`.

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
3. The returned `value` replaces the value to store. If `handled` is True, the library skips everything else on this path and uses `value` as the stored bytes. Otherwise it serializes `value`, calls `after_serialize` with the bytes, replaces them with the return value, and writes the result to Redis.

The value returned to the caller is always the original return value of the user function. The handler affects what is stored, not what is returned.

Unimplemented `before_serialize` degenerates to "serialize the original return value"; unimplemented `after_serialize` is then skipped.

### Read path

Runs only when the mode allows reading:

1. The library reads bytes from Redis.
2. No bytes → cache miss.
3. The library calls `before_deserialize` with the bytes.
4. The returned `value` replaces the working bytes. If `handled` is True, `value` is the final result: return it directly. If `handled` is False, deserialize `value`, call `after_deserialize` with the deserialized value, and return the replacement.

Unimplemented `before_deserialize` degenerates to "deserialize the bytes read from Redis"; unimplemented `after_deserialize` is then skipped.

## Interaction with Cache Mode

1. When reading is disabled, `before_deserialize` and `after_deserialize` are never called.
2. When writing is disabled, `before_serialize` and `after_serialize` are never called.
3. When both are disabled, no handler method is called.

This preserves the existing write-only, read-only, and disabled mode semantics.

## Error Handling

Handlers are orthogonal to `ignore_redis_errors`, and handler errors are **entirely the application's responsibility**:

1. Redis errors from the library's own get/put are handled by the existing logic and are not routed through the handler.
2. Exceptions raised by a handler propagate to the caller. The library provides **no** retry, fallback, degradation, or error counting for handler failures. A handler that wants to degrade should catch its own exceptions and return `handled=False` (before-boundaries) or the original value (after-boundaries) to fall back to the library default.

## Sync and Async Methods

The interface uses **paired method names**, with **no async-to-sync fallback**:

1. The synchronous path calls the non-`_async` methods. These **must not** be coroutine functions; the library calls them without awaiting. Violations raise `TypeError` at construction.
2. The asynchronous path calls **only** the `*_async` methods, which **must** be coroutine functions; the library awaits them. A handler used with an async cache must support the `*_async` boundaries it cares about; reaching an unsupported boundary raises whatever the implementation raises (by convention, `NotImplementedError`).
3. A sync-only handler therefore works **only** with synchronous caches. On an asynchronous cache, reaching an unimplemented `*_async` boundary surfaces the implementation's own failure (a missing attribute, or `NotImplementedError` by convention). This is deliberate: the alternative — awaiting or running sync methods on the event loop — invites blocking I/O inside async code.
4. A handler may mix sync and async methods freely across boundaries.

## No Runtime Validation

The library performs **no** runtime validation of handler behavior — no shape checks at registration, no return-value checks at invocation. The type annotations on `HandlerProtocol` are the contract; mypy (or any type checker) is the enforcement. If a handler misbehaves — wrong return shape, wrong types — the resulting error surfaces naturally and is the application's responsibility, consistent with the error-handling policy above. The library does not stand in the way of handlers that bend the rules deliberately.

## Registration

The instance-level handler is provided at construction time via the optional `handler` argument. A per-function override is available on `decorate`:

```python
cache = RedisFuncCache("name", LruPolicy(), factory=factory, handler=my_handler)  # instance-level

@cache.decorate(handler=offload_handler)  # per-function override
def big_payload_function(...): ...
```

Precedence: the `decorate(handler=...)` value wins when given; otherwise the instance-level handler applies.

With no handler at any level, behavior is identical to before the handler system existed.

`HandlerProtocol` and `HandlerContext` are exported from the package root:

```python
from redis_func_cache import HandlerContext, HandlerProtocol, RedisFuncCache
```

## Example: Object Storage Offload

Implement two methods: `before_serialize` and `before_deserialize`.

**Write** — in `before_serialize`: if the value is small, return `(False, value)` and the library stores it in Redis as usual. If it is large, upload the payload to object storage (using `ctx.args` / `ctx.kwds` to build a stable reference), build a small encoded reference (bytes), and return `(True, reference_bytes)`. The library skips its serializer and `after_serialize`, and stores only the reference.

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

Rejected in favor of a **frozen** dataclass. Keyword-only flat parameters (`keys=`, `hash_value=`, `func=`, `args=`, `kwds=`) were considered first, but adding any future field to them would be a breaking change for every third-party handler. A frozen dataclass is forward-compatible and removes shared-mutable-state concerns.

### A middleware chain

Rejected. Target use cases are transformations at specific boundaries, not wrapping the execution flow. A middleware chain would restructure the core path and introduce a second extension model alongside policy and serializer.

### Runtime coroutine detection on a single set of method names

Rejected in favor of paired `*_async` names. Runtime detection branches on every call, makes registration-time validation impossible, and obscures whether a handler is safe from a synchronous context. Paired names make the contract explicit and checkable at construction.

### Runtime validation of handler behavior

Rejected. Registration-time shape checks and invocation-time return checks add library code whose only purpose is to catch contract violations that a type checker already catches statically, and they stand in the way of handlers that deliberately bend the rules. The annotations on `HandlerProtocol` are the contract; misbehavior surfaces as natural Python errors and is the application's responsibility.

### A base handler with no-op default implementations

Rejected (including the intermediate design of a Protocol carrying default method bodies — a conflation of `Protocol`, which is purely structural, with `ABC`, which is nominal and may carry implementations). Defaults would force the library to pick a behavior for unsupported boundaries and push handlers into inheritance. Instead, `HandlerProtocol` is pure and implementations `raise NotImplementedError` for boundaries they do not support — the standard file-like-object pattern, with no runtime machinery in the library.

### Async-to-sync fallback on the asynchronous path

Rejected. The fallback invites blocking synchronous I/O (the exact problem the handler system exists to solve) to run silently on the event loop, with no warning. Requiring explicit `*_async` methods keeps the contract honest: an async cache gets explicitly async handler code, or the library default.

### Entry format version / generation tags

Rejected as a library concern. Versioning of handler-written bytes is an application responsibility; the library offers no metadata channel.

## Open Questions

1. Should the protocol be a runtime-checkable Protocol, an ABC, or plain duck typing. *(Current: pure, non-runtime-checkable structural Protocol; implementations are duck-typed and need not inherit.)*

## Implementation Plan

1. Define the handler protocol with four boundaries, sync/async pairs, and the two return conventions. *(Done: `HandlerProtocol` in `handler.py`.)*
2. Frozen `HandlerContext` dataclass passed to every handler method. *(Done.)*
3. Optional `handler` argument on the cache constructor, plus a per-function override on `decorate`. *(Done.)*
4. No runtime validation of handler behavior; typing is the contract. *(Done: `validate_handler` removed.)*
5. Insert handler calls at the four boundaries in both execution paths, statically, one to one. *(Done: direct calls in `exec` / `aexec`.)*
6. Uniform short-circuit rule: `handled=True` skips the library's remaining steps on that side, including the `after_*` method. *(Done.)*
7. Handler context uses the same excludes-filtered effective arguments as key calculation. *(Done.)*
8. Respect cache mode. *(Done: handlers only run inside `mode.read` / `mode.write`.)*
9. Tests: no handler, full handler, subsets, sync/async, `handled` True/False per boundary, short-circuit, per-function override, mode interaction, frozen context. *(Done: `tests/test_handler.py`.)*
10. Document the handler system and offload use case in the README. *(Done.)*
11. Export `HandlerProtocol` and `HandlerContext` from the package root. *(Done.)*

## References

1. Existing serializer API: the `serializer` argument of the cache constructor.
2. Existing sync/async split documented in the README.
3. Related design note: caching large values in Redis is an anti-pattern.
4. Implementation: `src/redis_func_cache/handler.py` (pure `HandlerProtocol`, `HandlerContext`), `src/redis_func_cache/cache.py` (static call sites in `exec` / `aexec` / `decorate`).
5. Tests: `tests/test_handler.py`.
