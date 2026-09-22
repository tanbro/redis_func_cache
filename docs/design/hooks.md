# Proposal: Hook System for `redis_func_cache`

## Summary

Introduce a **hook system** around the existing `(serialize, deserialize)` serializer pair, allowing application code to inject logic at key points in the cache-entry lifecycle: before/after store, before/after load, and on failure.

The goal is to keep `redis_func_cache` a pure "function-level cache" primitive while giving applications a clean extension point for concerns that are **out of scope for the library itself**, such as:

- Storing large values outside Redis (S3-like object storage) and caching only a small reference.
- Custom cleanup when a cached entry is evicted.
- Failure handling and fallback strategies for external storage.
- Metrics, logging, and tracing at cache boundaries.

## Motivation

### Current limitation

The current extension point is the `serializer` argument, which accepts a `(serialize, deserialize)` tuple of plain functions:

```python
cache = RedisFuncCache(
    __name__,
    LruTPolicy(),
    factory=lambda: Redis.from_url("redis://"),
    serializer=(serialize, deserialize),
)
```

This is too low-level for several real-world use cases:
- Synchronous-only. serialize must return a value immediately. Any I/O (e.g. writing to object storage) blocks the caller or the event loop.
- No lifecycle hooks. There is no place to run logic before serialization or after deserialization.
- No failure strategy. If serialization or an external store fails, the library has no defined fallback — it can only propagate the exception.
- No context. The serializer does not receive information about the decorated function, its arguments, or the TTL, which are often needed to build stable storage keys.

#### Concrete use case
An application caches the result of a function that returns a multi-megabyte HTML page.
Caching the page directly in Redis is an abuse: it consumes Redis memory, blocks the single-threaded event loop on large reads/writes, and slows replication.

The desired design is a two-tier cache:
- Redis stores only a small reference (a pointer) plus metadata.
- Object storage (S3-like) stores the actual payload.

redis_func_cache should manage the Redis side — key computation, eviction policy, TTL, concurrency control — without knowing anything about S3.

A hook system provides exactly the extension point needed: the application replaces the large value with a small reference on the write path, and resolves the reference back to the value on the read path.

#### Design Goals
Backward compatible. No hooks configured ⇒ behavior identical to today.

- Composable. Multiple hooks can be registered and run in order.
- Symmetric. Hooks exist on both the write path and the read path.
- Async-aware. Hooks work for both synchronous and asynchronous decorated functions, mirroring the library's existing sync/async split.
- Non-invasive. The core cache logic (key calculation, Lua scripts, eviction) is unchanged.
- Explicit failure handling. Applications can define fallback behavior for hook failures.

Non-Goals:
- Built-in S3 support. The library must not depend on any specific object store.

A general middleware framework. Hooks are scoped to the cache-entry lifecycle only.

Changes to the eviction algorithm or Redis data structures.

#### Lifecycle and Hook Points

Write path (cache miss, after the user function returns)

```text
user function returns value
        │
        ▼
 ┌──────────────────┐
 │  before_store    │  may transform value → value | ref
 └──────────────────┘
        │
        ▼
 ┌──────────────────┐
 │    serialize     │  existing serializer (unchanged)
 └──────────────────┘
        │
        ▼
 ┌──────────────────┐
 │   after_store    │  side effects only (metrics, logs, etc.)
 └──────────────────┘
        │
        ▼
   write to Redis
```

Read path (cache hit)

```text
   read from Redis
        │
        ▼
 ┌──────────────────┐
 │   before_load    │  may inspect or validate ref
 └──────────────────┘
        │
        ▼
 ┌──────────────────┐
 │   deserialize    │  existing deserializer (unchanged)
 └──────────────────┘
        │
        ▼
 ┌──────────────────┐
 │   after_load     │  may transform ref → value
 └──────────────────┘
        │
        ▼
   return to caller
```

Failure path

```text
 any stage raises
        │
        ▼
 ┌──────────────────┐
 │    on_error      │  decide: fallback value, re-raise, or skip cache
 └──────────────────┘
```

Eviction path (optional, for future consideration)

```text
   entry evicted from Redis
        │
        ▼
 ┌──────────────────┐
 │    on_evict      │  side effects only
 └──────────────────┘
```

> Note: Redis does not emit events for evictions performed by Lua scripts. on_evict can only be triggered reliably for explicit operations such as purge() and vacuum(), or via Redis keyspace notifications when available. This hook is therefore listed as a future extension and is out of scope for the initial implementation.

### API Sketch

#### Hook protocol

```python
from typing import Any, Protocol

class CacheHook(Protocol):
    def before_store(self, value: Any, context: "HookContext") -> Any:
        """Transform the value before serialization. Return the value unchanged by default."""

    def after_store(self, ref: Any, context: "HookContext") -> None:
        """Called after a successful Redis write. Side effects only."""

    def before_load(self, ref: Any, context: "HookContext") -> Any:
        """Inspect or validate the reference before deserialization."""

    def after_load(self, ref: Any, value: Any, context: "HookContext") -> Any:
        """Transform the deserialized value before returning it to the caller."""

    def on_error(self, stage: str, exc: Exception, context: "HookContext") -> Any:
        """Handle an error. May return a fallback value or re-raise."""
```

#### Hook context

```python
@dataclass(frozen=True)
class HookContext:
    cache_name: str
    func: Callable[..., Any]
    args: tuple[Any, ...]
    kwargs: dict[str, Any]
    ttl: int | None
    # possibly: policy name, serializer name, etc.
```

The context is read-only from the hook's perspective. It gives hooks enough information to build deterministic storage keys and to make decisions based on the call site.

#### Registration
Hooks are registered on the cache instance:

```python
cache = RedisFuncCache(
    __name__,
    LruTPolicy(),
    factory=lambda: Redis.from_url("redis://"),
)

cache.add_hook(S3OffloadHook(bucket="my-cache-bucket"))
```

Multiple hooks run in registration order for each hook point.

Alternatively, hooks may be passed at construction time:

```python
cache = RedisFuncCache(
    __name__,
    LruTPolicy(),
    factory=lambda: Redis.from_url("redis://"),
    hooks=[S3OffloadHook(bucket="my-cache-bucket")],
)
```

#### Async hooks

To mirror the library's sync/async split, hooks may be declared as either sync or async:

- A synchronous cache invokes sync hooks directly.
- An asynchronous cache awaits async hooks.
- A hook that declares an async method while being used with a synchronous cache raises a clear error at registration time.

Example: S3 Offload Hook

```python
class S3OffloadHook:
    """Store large values in S3, cache only a reference in Redis."""

    def __init__(self, bucket: str, threshold: int = 1 << 20):
        self.bucket = bucket
        self.threshold = threshold
        self.s3 = boto3.client("s3")

    def before_store(self, value, context):
        payload = json.dumps(value).encode()
        if len(payload) < self.threshold:
            return value  # small enough, keep in Redis
        key = self._build_key(context)
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=payload)
        return {"__s3_ref__": key}

    def after_load(self, ref, value, context):
        if isinstance(value, dict) and "__s3_ref__" in value:
            obj = self.s3.get_object(Bucket=self.bucket, Key=value["__s3_ref__"])
            return json.loads(obj["Body"].read())
        return value

    def on_error(self, stage, exc, context):
        # Fall back to executing the function directly on S3 failure.
        if stage in {"after_load", "before_load"}:
            return _MISS
        raise

    def _build_key(self, context):
        return f"{context.cache_name}/{context.func.__qualname__}/{hash_call(context)}"
```

The library remains unaware of S3. It only sees a small dict on the Redis side.


### Error Semantics
Each hook point has a defined failure contract:

Hook | On exception
---- | ------------
before_store | Call on_error; if it returns a value, store that; if it re-raises, propagate.
after_store | Call on_error; the Redis write already happened, so the error cannot undo it.
before_load | Call on_error; if it returns MISS, treat as a cache miss and execute the function.
after_load | Call on_error; if it returns a value, return that; otherwise propagate.
on_error | If it raises, the new exception propagates.

A sentinel value such as `MISS` (or a dedicated exception) signals "treat as cache miss" so applications can implement graceful degradation.

### Backward Compatibility
- With no hooks registered, the code path is exactly as before: serialize → Redis → deserialize.
- Existing serializer arguments continue to work unchanged.
- The hook system is additive; it does not replace or deprecate any existing API

### Alternatives Considered

#### Extend serializer to async callables
Rejected: it does not provide lifecycle points and conflates "encoding" with "external I/O and failure handling".

#### Subclass RedisFuncCache
Rejected: forces applications to subclass and override internals, which is brittle and couples application code to library internals.

#### Middleware-style plugin framework
Rejected: too heavy for the scope. Hooks scoped to the cache-entry lifecycle are sufficient.

## Open Questions
- Should hooks be allowed to short-circuit the cache entirely (e.g. skip Redis on write)?
- Should HookContext include a mutable metadata dict that hooks can use to pass data between stages?
- Should on_evict be implemented via Redis keyspace notifications, or left to the application?
- How should hook ordering interact with per-function serializer overrides?
- Should there be a built-in SizeGuardHook as a reference implementation?

## Implementation Plan
- Define CacheHook protocol and HookContext dataclass.
- Add hooks argument to RedisFuncCache.__init__ and an add_hook method.
- Insert hook invocation into the existing exec / aexec paths.
- Define MISS sentinel and error semantics.
- Add tests covering: no hooks, single hook, multiple hooks, sync/async, and error paths.
- Document the hook system in the README with the S3 offload example.

## References
- Existing serializer API: RedisFuncCache(..., serializer=(serialize, deserialize))
- Existing sync/async split documented in README.
- Related discussion: caching large values in Redis is an anti-pattern; references available in the project's design notes.
