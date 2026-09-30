---
status: accepted
create_at: 2026-09-22
updated_at: 2026-09-23
---

# Proposal: Handler System for `redis_func_cache`

> **Usage documentation:** how to write and register a handler — the four
> boundaries, return conventions, write/read path sequence diagrams, and the
> object-storage offload example — lives in the user guide,
> `docs/usage/handlers.md`. This document is the design record: motivation,
> goals, and the alternatives that were rejected.

## Summary

Introduce a single, optional **handler** that wraps the four serialization boundaries of the cache: before serialize, after serialize, before deserialize, after deserialize.

The driving use case is **offloading large values to object storage**: Redis stores only a small reference; the application resolves it back on read. The library never learns about the object store.

A handler is an active extension point, not a passive callback: when it reports that it has handled a boundary, the library skips **all** of its own remaining steps on that side, including the corresponding `after_*` method.

## Motivation

The existing extension point is the `serializer` argument — a pair of plain functions `(serialize, deserialize)`. Three properties of that API block the offload use case:

1. **Synchronous only.** A serializer must return immediately. Writing to or reading from object storage is I/O; doing it synchronously blocks the caller or the event loop.
2. **No call context.** A serializer receives only the value. It cannot see the cache keys, hash field, decorated function, or invocation arguments — all of which an offload handler typically needs to build a storage key or path.
3. **All-or-nothing.** Providing a custom serializer replaces both directions. There is no way to take over only the write path (or only the read path) while keeping the library's default encoding on the other side.

A handler addresses all three: it supports async methods, receives a call context, and **can take over each of the four boundaries individually** — at any boundary it does not take over (identity, or `handled=False`), the library's own default step runs unchanged.

### Concrete use case

An application caches the result of a function that returns a multi-megabyte HTML page.

Caching the page directly in Redis is an abuse: it consumes Redis memory, blocks the single-threaded event loop on large reads and writes, and slows replication. The desired design is a two-tier cache. Redis stores only a small reference plus metadata; object storage stores the actual payload. The library manages the Redis side — key computation, eviction policy, TTL, concurrency control — and knows nothing about object storage.

On the write path the handler replaces the large value with a small reference. On the read path it resolves the reference back to the value and takes over deserialization.

## Design Goals

1. Backward compatible. With no handler configured, behavior is identical to today.
2. Single handler. Exactly one handler per execution — the cache instance's handler, optionally overridden per decorated function. No chains, no ordering rules, no composition inside the library.
3. Symmetric. Handlers exist on both the write path and the read path, with one uniform short-circuit rule (see Return Conventions in the usage documentation).
4. Async aware. Handlers work for both synchronous and asynchronous decorated functions, via paired sync and `*_async` methods. There is **no** async-to-sync fallback: the asynchronous path calls only `*_async` methods.
5. Non-invasive. The core cache logic — key calculation, Lua scripts, eviction — is unchanged; the serializer hot path is untouched.
6. Static contract. The type annotations on `HandlerProtocol` are the contract, checked statically. An implementation provides at least one method group — sync or `*_async` — matching its execution path (both when it serves both paths), and the group it does not use may be kept as `raise NotImplementedError` placeholders. Within a provided group every method is defined, and a boundary it does not need returns its identity value (`before_*` → `(False, value)`, `after_*` → `return value`).

## Non-Goals

1. Built-in object storage support. The library must not depend on any specific object store.
2. Multiple handlers. Composition, if needed, is the application's responsibility.
3. A general middleware framework. Handlers are scoped to the four serialization boundaries only.
4. Changes to the eviction algorithm or Redis data structures.
5. Per-value write suppression. A handler can change _what_ is written but cannot prevent the write. Skipping the write for a particular result is the caller's job (cache mode, or not calling the cached function path).
6. Failure policy. The library does not retry, degrade, count, or fall back on handler errors — see Error Handling in the usage documentation. Reliability policy belongs entirely to the application.
7. Entry format versioning. Version or generation tags for handler-written bytes are the application's concern; the library offers no metadata channel for them.

## Backward Compatibility

1. With no handler, the code path is exactly as before.
2. Existing serializer arguments work unchanged. A handler and a serializer may be combined: the serializer defines the default encoding for `handled=False`; the handler may replace bytes at any boundary.
3. The handler system is additive; it replaces and deprecates nothing.

## Alternatives Considered

### Extending the serializer to async callables

Rejected. Making `serializer` accept async callables would force the core `serialize()` hot path to branch on coroutine-ness and await — an invasive change to the hottest code in the library — and a serializer pair still cannot expose call context or allow taking over only one direction while keeping the library default on the other. The handler keeps the serializer path untouched and covers all three motivation points.

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

Rejected in favor of paired `*_async` names. Runtime detection branches on every call, makes registration-time validation impossible, and obscures whether a handler is safe from a synchronous context. Paired names make the contract explicit and statically checkable.

### Runtime validation of handler behavior

Rejected. Registration-time shape checks and invocation-time return checks add library code whose only purpose is to catch contract violations that a type checker already catches statically, and they stand in the way of handlers that deliberately bend the rules. The annotations on `HandlerProtocol` are the contract; misbehavior surfaces as natural Python errors and is the application's responsibility.

### A base handler with no-op default implementations

Rejected (including the intermediate design of a Protocol carrying default method bodies — a conflation of `Protocol`, which is purely structural, with `ABC`, which is nominal and may carry implementations). Defaults would force the library to pick a behavior for unsupported boundaries and push handlers into inheritance. Instead, `HandlerProtocol` is pure: an implementation provides the group its execution path uses — every method of that group defined, identity returns where the boundary is unused — and keeps the group it does not use as `raise NotImplementedError` placeholders, with no runtime machinery in the library.

### Async-to-sync fallback on the asynchronous path

Rejected. The fallback invites blocking synchronous I/O (the exact problem the handler system exists to solve) to run silently on the event loop, with no warning. Requiring explicit `*_async` methods keeps the contract honest: an async cache gets explicitly async handler code, or the library default.

### Entry format version / generation tags

Rejected as a library concern. Versioning of handler-written bytes is an application responsibility; the library offers no metadata channel.

## Open Questions

1. Should the protocol be a runtime-checkable Protocol, an ABC, or plain duck typing. _(Current: pure, non-runtime-checkable structural Protocol; implementations are duck-typed and need not inherit.)_

## Implementation Plan

1. Define the handler protocol with four boundaries, sync/async pairs, and the two return conventions. _(Done: `HandlerProtocol` in `handler.py`.)_
2. Frozen `HandlerContext` dataclass passed to every handler method. _(Done.)_
3. Optional `handler` argument on the cache constructor, plus a per-function override on `decorate`. _(Done.)_
4. No runtime validation of handler behavior; typing is the contract. _(Done: `validate_handler` removed.)_
5. Insert handler calls at the four boundaries in both execution paths, statically, one to one. _(Done: direct calls in `exec` / `aexec`.)_
6. Uniform short-circuit rule: `handled=True` skips the library's remaining steps on that side, including the `after_*` method. _(Done.)_
7. Handler context uses the same excludes-filtered effective arguments as key calculation. _(Done.)_
8. Respect cache mode. _(Done: handlers only run inside `mode.read` / `mode.write`.)_
9. Tests: no handler, full handler, identity-only boundaries, sync/async, `handled` True/False per boundary, short-circuit, per-function override, mode interaction, frozen context. _(Done: `tests/test_handler.py`.)_
10. Document the handler system and offload use case in the user guide. _(Done: `docs/usage/handlers.md`.)_
11. Export `HandlerProtocol` and `HandlerContext` from the package root. _(Done.)_

## References

1. Usage documentation: `docs/usage/handlers.md`.
2. Existing serializer API: the `serializer` argument of the cache constructor.
3. Related design note: caching large values in Redis is an anti-pattern.
4. Implementation: `src/redis_func_cache/handler.py` (pure `HandlerProtocol`, `HandlerContext`), `src/redis_func_cache/cache.py` (static call sites in `exec` / `aexec` / `decorate`).
5. Tests: `tests/test_handler.py`.
