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
4. Uniform return convention. Every handler method returns a pair of a boolean and a value.
5. Async aware. Handlers work for both synchronous and asynchronous decorated functions, mirroring the library's existing sync and async split.
6. Non-invasive. The core cache logic, including key calculation, Lua scripts, and eviction, is unchanged.

## Non-Goals

1. Built-in object storage support. The library must not depend on any specific object store.
2. Multiple handlers. Composition, if needed, is the application's responsibility.
3. A general middleware framework. Handlers are scoped to the four serialization boundaries only.
4. Changes to the eviction algorithm or Redis data structures.

## The Four Handler Methods

The handler protocol defines four methods. All four are optional. A handler may implement only the ones it needs.

1. before_serialize. Called on the write path, after the user function returns and before the library serializes the value.
2. after_serialize. Called on the write path, after the library serializes the value and before the library writes it to Redis.
3. before_deserialize. Called on the read path, after the library reads bytes from Redis and before the library deserializes them.
4. after_deserialize. Called on the read path, after the library deserializes the bytes and before the value is returned to the caller.

## Return Convention

Every handler method returns a tuple of two elements: a boolean and a value. The convention is uniform across all four methods.

The boolean is named **handled**. The value is named **value**.

When `handled` is True, the handler has taken over the boundary. The library uses the returned value and does not perform its own default operation at that boundary.

When `handled` is False, the handler has not taken over the boundary. The library ignores the returned value and performs its own default operation.

### Per-method meaning of handled

before_serialize:

- `handled` True: the library serializes the returned value instead of the original return value of the user function.
- `handled` False: the library serializes the original return value of the user function.

after_serialize:

- `handled` True: the library writes the returned bytes to Redis instead of the bytes produced by its own serializer.
- `handled` False: the library writes the bytes produced by its own serializer.

before_deserialize:

- `handled` True: the returned value is treated as the final value. The library skips its own deserialize step and does not call after_deserialize.
- `handled` False: the returned value is treated as bytes and the library proceeds with its own deserialize step.

after_deserialize:

- `handled` True: the library returns the returned value to the caller instead of the value produced by its own deserializer.
- `handled` False: the library returns the value produced by its own deserializer.

### Return value when handled is False

When `handled` is False, the returned value is ignored by the library. A handler should return the value it received, unchanged, to make the intent explicit. The library must not depend on this value.

## Read Path and Write Path

### Write path

The write path runs only when the mode allows writing. The sequence is:

1. The user function is executed and returns a value.
2. The library calls before_serialize with the return value.
3. If `handled` is True, the value to serialize is the one returned by the handler. Otherwise it is the original return value.
4. The library serializes the value to bytes.
5. The library calls after_serialize with the bytes.
6. If `handled` is True, the bytes to store are the ones returned by the handler. Otherwise they are the bytes produced by the library serializer.
7. The library writes the bytes to Redis.

The value returned to the caller is always the original return value of the user function. The handler affects what is stored, not what is returned.

### Read path

The read path runs only when the mode allows reading. The sequence is:

1. The library reads bytes from Redis.
2. If no bytes are found, the library treats it as a cache miss.
3. The library calls before_deserialize with the bytes.
4. If `handled` is True, the value returned by the handler is treated as the final value. The library skips the next two steps and returns this value.
5. If `handled` is False, the library deserializes the bytes.
6. The library calls after_deserialize with the deserialized value.
7. If `handled` is True, the value returned by the handler is returned to the caller. Otherwise the deserialized value is returned.

## Interaction with Cache Mode

The cache mode controls whether reading and writing are allowed. Handlers must respect the mode.

1. When reading is disabled, before_deserialize and after_deserialize are never called.
2. When writing is disabled, before_serialize and after_serialize are never called.
3. When both are disabled, no handler method is called.

This preserves the existing semantics of write only, read only, and disabled modes.

## Interaction with Redis Error Handling

The existing ignore_redis_errors option controls how Redis errors are handled. Handlers are orthogonal to this option.

1. Redis errors raised by the library's own get and put operations are handled by the existing logic and are not routed through the handler.
2. Exceptions raised by the handler itself are propagated to the caller. The handler is responsible for its own error handling.
3. A handler may choose to catch its own exceptions and return `handled` False to fall back to the library's default behavior.

## Async Support

Handlers must work for both synchronous and asynchronous decorated functions.

1. A synchronous cache calls handler methods synchronously. If a handler method is a coroutine function, the library raises an error at registration time.
2. An asynchronous cache awaits handler methods if they are coroutine functions, and calls them directly otherwise.
3. A handler may implement some methods as synchronous and others as asynchronous. The library decides how to call each method based on whether it is a coroutine function.

## Registration

A handler is provided at cache construction time.

The cache accepts an optional handler argument. When it is not provided, behavior is identical to the current implementation.

A cache instance holds at most one handler. There is no method to add a second handler after construction. This is intentional, to keep the semantics simple and unambiguous.

## Example Use Case: Object Storage Offload

This section describes how the handler system supports the object storage offload use case, without prescribing any specific storage backend.

A handler is implemented with two methods: before_serialize and before_deserialize.

In before_serialize, the handler inspects the value returned by the user function. If the value is small, the handler returns handled False and the library stores it in Redis as usual. If the value is large, the handler writes the payload to object storage, builds a small reference, and returns `handled` True with the reference as the value. The library then serializes and stores only the small reference in Redis.

In before_deserialize, the handler inspects the bytes read from Redis. If the bytes represent a small value, the handler returns handled False and the library deserializes them as usual. If the bytes represent a reference, the handler fetches the payload from object storage, parses it, and returns `handled` True with the final value. The library skips its own deserialize step and returns the value directly.

The library remains unaware of object storage. It only sees a small value on the write path and a final value on the read path.

## Backward Compatibility

1. With no handler configured, the code path is exactly as before. The library serializes, writes, reads, and deserializes as it does today.
2. Existing serializer arguments continue to work unchanged. A handler and a serializer may be used together. The serializer defines the default encoding, and the handler may override it at any boundary.
3. The handler system is additive. It does not replace or deprecate any existing API.

## Alternatives Considered

### Extending the serializer to async callables

Rejected. It does not provide lifecycle points and conflates encoding with external I/O and failure handling.

### Multiple hooks with a chain

Rejected. It introduces ordering rules, composition semantics, and ambiguity when more than one hook wants to take over the same boundary. A single handler is sufficient for the target use cases, and composition can be implemented by the application if needed.

### A sentinel value to signal bypass

Rejected. The normal path of before_deserialize already needs to return a value, which conflicts with the use of a sentinel to mean "no value". A uniform `handled` boolean avoids this conflict.

### Raising a special exception to signal bypass

Rejected. It uses exceptions for control flow, complicates testing, and does not extend naturally to the other three boundaries.

### A mutable context object shared across boundaries

Rejected for now. It introduces a new concept and shared mutable state. The uniform `handled` boolean is simpler and sufficient for the target use cases. A context object may be added later as an additive extension if a real need arises.

### A middleware chain

Rejected. The target use cases are transformations at specific boundaries, not wrapping the entire execution flow. A middleware chain would require restructuring the core execution path and introduces a second extension model alongside the existing policy and serializer mechanisms.

## Open Questions

1. Should the handler protocol be a runtime-checkable Protocol, an abstract base class, or a plain duck-typed interface.
2. Should the library provide a no-op base handler that applications can subclass and override selectively.
3. Should the handler receive additional context, such as the decorated function, its arguments, the cache keys, or the hash value, in addition to the value being processed.
4. Should the library validate at registration time that the handler implements at least one method, or that any async methods are compatible with the cache's sync or async nature.
5. Should the value returned by a handler when `handled` is False be required to equal the input value, or may it be anything and simply ignored.

## Implementation Plan

1. Define the handler protocol with the four methods and the uniform return convention.
2. Add an optional handler argument to the cache constructor.
3. Validate the handler at construction time, including the sync and async compatibility of its methods.
4. Insert handler calls into the existing synchronous and asynchronous execution paths at the four boundaries.
5. Respect the cache mode when deciding whether to call each handler method.
6. Add tests covering: no handler, handler with all methods, handler with a subset of methods, synchronous and asynchronous handlers, `handled` True and `handled` False at each boundary, and interaction with cache mode.
7. Document the handler system and the object storage offload use case in the README.

## References

1. Existing serializer API: the serializer argument of the cache constructor.
2. Existing sync and async split documented in the README.
3. Related design note: caching large values in Redis is an anti-pattern.
