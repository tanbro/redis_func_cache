# Important Considerations


Before using this library, please be aware of the following important considerations:

## Cache Stampede Risk

> ⚠️ **Important:** \
> When a cached function is expensive and called concurrently with the same arguments, multiple calls may execute simultaneously if the cache is empty or expired. This is known as **"cache stampede"** or **"thundering herd"** problem.

### Understanding the Problem

While the library ensures atomicity of individual Redis operations (via Lua scripts), there is a race condition window between:

1. Checking the cache (returning `None`)
2. Executing the user function
3. Writing the result to cache

When multiple concurrent requests with identical arguments arrive simultaneously:

```
Thread A: cache miss → execute expensive function (5s) → write to cache
Thread B: cache miss → execute expensive function (5s) → write to cache
Thread C: cache miss → execute expensive function (5s) → write to cache
...
```

This behavior is **by design**. The library's responsibility is to manage cache storage efficiently, not to control application-level concurrency. Concurrency control strategies depend heavily on your specific use case, deployment environment, and latency requirements.

### Mitigation Strategies

Since this is fundamentally an **application-level concern**, the mitigation strategy should be chosen and implemented by you based on your requirements:

#### Strategy 1: Redis Distributed Lock (Recommended for Distributed Systems)

Use Redis locks to ensure only one thread executes the expensive function:

```python
import time
from redis import Redis
from redis_func_cache import RedisFuncCache, LruTPolicy

factory = lambda: Redis.from_url("redis://")
cache = RedisFuncCache("my-cache", LruTPolicy(), factory=factory)


@cache
def expensive_function(x: int) -> int:
    # Acquire lock before executing expensive operation
    lock_key = f"lock:expensive_function:{x}"
    redis_client = Redis.from_url("redis://")
    lock = redis_client.lock(lock_key, timeout=30, blocking_timeout=5)

    try:
        if lock.acquire():
            # Double-check: cache might have been populated while waiting
            # (You would need to implement a cache re-check here)
            return x * x  # Your expensive operation
        else:
            # Couldn't acquire lock - wait and retry
            time.sleep(0.1)
            # Re-fetch from cache or raise exception
            raise TimeoutError("Cache lookup timeout")
    finally:
        if lock.locked():
            lock.release()
```

#### Strategy 2: Semaphore (For Single-Process Concurrency)

For single-process scenarios, use Python's threading primitive:

```python
from threading import Semaphore
from redis_func_cache import RedisFuncCache, LruTPolicy

cache = RedisFuncCache("my-cache", LruTPolicy(), redis_client=redis_client)

# Limit concurrent executions to 1
semaphore = Semaphore(1)


@cache
def expensive_function(x: int) -> int:
    with semaphore:
        # Only one thread can execute this block at a time
        return x * x  # Your expensive operation
```

#### Strategy 3: TTL Jitter

Add random jitter to cache expiration to prevent simultaneous expirations:

```python
import random
from redis_func_cache import RedisFuncCache, LruTPolicy

# Base TTL + random jitter (0-60 seconds)
cache = RedisFuncCache("my-cache", LruTPolicy(), redis_client=redis_client, ttl=300 + random.randint(0, 60))
```

#### Strategy 4: Stale-While-Revalidate (Advanced)

Allow returning slightly stale data while refreshing the cache in the background. This requires custom implementation outside the library's core functionality.

### Choosing the Right Strategy

| Strategy               | Best For                                     | Trade-offs                                 |
| ---------------------- | -------------------------------------------- | ------------------------------------------ |
| Redis Lock             | Distributed systems, long-running functions  | Adds latency for waiting threads           |
| Semaphore              | Single-process scenarios                     | Not suitable for multi-process deployments |
| TTL Jitter             | Preventing mass expiration                   | Doesn't prevent stampede on cold cache     |
| Stale-While-Revalidate | Read-heavy workloads, tolerant of stale data | Requires complex implementation            |

> 💡 **Recommendation:** Start with **Strategy 1 (Redis Lock)** for most distributed applications. It provides the best balance between correctness and usability.

For more detailed examples and advanced patterns, see [Important Considerations - Cache Stampede Risk](#important-considerations).

## Redis Client Lifecycle

The cache issues single Lua script invocations through the [redis-py][] client you supply (directly, or via `factory` for each operation). It does **not** manage connections, threads or event loops — those semantics are defined by redis-py, and how you wire the client is your application's decision. Please consult the redis-py documentation for your client type; the main points, at the time of writing:

- **Synchronous `redis.Redis`** is thread-safe for command execution: each command runs on a connection drawn from the client's [`ConnectionPool`](https://redis-py.readthedocs.io/en/stable/connections.html#connection-pool), so one client (and its pool) may be shared across threads.
- **`Pipeline` and `PubSub` objects** carry per-object state and must not be shared across threads. This library never creates them, but your own code should.
- **`redis.asyncio` clients are bound to the event loop that created them.** Sharing one client or pool across event loops is undefined behavior. In multi-loop deployments (e.g. one loop per worker), create an independent pool per loop.
- **Fork safety**: connections inherited across `fork()` are shared by two processes and corrupt silently. Rebuild the pool in the child process.

Practical guidance for the `factory` argument:

- The factory is invoked every time the cache needs a client, so it should return a **lightweight client sharing one pre-configured pool** — e.g. `redis.Redis.from_pool(pool)` — never construct a new pool per call. Creating a pool (or connection) per invocation leaks connections and defeats redis-py's server-side Lua script cache (`EVALSHA` falls back to `EVAL` for each fresh client).
- All clients produced by one factory must address the same logical Redis dataset, otherwise cache keys and bookkeeping are scattered across servers.

## Other Key Limitations

- **Generator functions** are not supported.
- **Decorator compatibility** with other decorators is not guaranteed.
- **Unique cache names**: Each [`RedisFuncCache`][] instance must have a unique `name` argument. Sharing the same name across different instances may lead to serious errors.

## Known Issues


- Arguments passed to a cached function — including `self`/`cls` when decorating methods inside a class body — must be serializable by the args serializer of the policy's hash mixin (pickle for the built-in policies, JSON for the `Json*` mixins), or excluded from the key and hash calculations with `excludes` and/or `excludes_positional`.

  - Instance methods: the instance is hashed **by value**. If the result does not depend on instance state, use `excludes_positional=[0]` — cache entries are then shared across instances; otherwise the instance must be serializable.
  - Class methods: classes pickle **by reference**, so importable classes work out of the box. Place `@classmethod` outside the cache decorator to preserve descriptor binding. If the result does not depend on the declaring class or subclass, use `excludes_positional=[0]` to keep `cls` out of the cache key:

    ```python
    class MyClass:
        @classmethod
        @cache(excludes_positional=[0])
        def cm(cls, value): ...
    ```
  - Passing an already-bound *instance* method (e.g. `cache.decorate(obj.method)`) raises `TypeError` at key calculation; decorate the unbound function in the class body instead.

- Compatibility with other [decorator][]s is not guaranteed.

- It cannot hit cache across different Python versions by default. Because:

  - The built-in policies use [`pickle`][] to serialize function arguments and then calculate the cache key by hashing the serialized data with `md5` by default.

    [`pickle`][] is chosen because only the hash bytes are stored in Redis, not the serialized data itself, making this approach safe. However, [`pickle`][] causes **incompatibility between different Python versions**.

  - The key calculation defined in `mixins.hash.AbstractHashMixin.calc_hash()` uses the function's bytecode as part of the hash computation by default. So it cannot hit cache across different Python versions.

  If your application needs to be compatible across Python versions, you should disable `use_bytecode` attribute of the mixin's `__hash_config__`, and use a [json][] based hash mixer. Or define your own hash policy using a version-compatible serialization method. For example:

  ```python
  from dataclasses import replace
  from redis_func_cache import RedisFuncCache as Cache
  from redis_func_cache.policies.abstract import BaseSinglePolicy
  from redis_func_cache.mixins.hash import JsonMd5HashMixin
  from redis_func_cache.mixins.scripts import LfuScriptsMixin


  class MyLfuPolicy(LfuScriptsMixin, JsonMd5HashMixin, BaseSinglePolicy):
      __key__ = "my-lfu"

      # Override hash config here !!!
      __hash_config__ = replace(JsonMd5HashMixin.__hash_config__, use_bytecode=False)


  cache = Cache(__name__, MyLfuPolicy(), factory=redis_client_factory)
  ```

  As shown above, the `JsonMd5HashMixin` uses [json][], which can be used across different Python versions, rather than [`pickle`][]. `use_bytecode` is set to `False` to avoid version compatible problems caused by bytecode.

- The cache eviction policies are mainly based on [Redis][] sorted set's score ordering. For most policies, the score is a positive integer. Its maximum value is `2^32-1` in [Redis][], which limits the number of times of eviction replacement. [Redis][] will return an `overflow` error when the score overflows.

- **Cache Stampede Risk:** Under high concurrency, multiple requests with identical arguments may simultaneously execute the decorated function when the cache is empty or expired. This is a **known limitation** by design—concurrency control is the responsibility of the application layer. See [Important Considerations - Cache Stampede Risk](#important-considerations) for mitigation strategies and code examples.

- Generator functions are not supported.

- If there are multiple [`RedisFuncCache`][] instances with the same name, they may share the same cache data.
  This may lead to serious errors, so we should avoid using the same `name` argument for different cache instances.

- The Redis keys generated by *Multiple* policies include a hash derived from Python bytecode, making them **incompatible across Python versions**.

  However, you can define a custom mixin that inherits from `AbstractHashMixin`, in which you can implement your own hash function to support compatibility across Python versions.

  Additionally, the decorator **cannot be used with native or built-in functions**: they carry no stable cross-process function identity for key calculation, so they are rejected with a `TypeError` — regardless of the `use_bytecode` setting.

[redis]: https://redis.io/ "Redis is an in-memory data store used by millions of developers as a cache"
[redis-py]: https://redis.io/docs/develop/clients/redis-py/ "Connect your Python application to a Redis database"

[decorator]: https://docs.python.org/glossary.html#term-decorator "A function returning another function, usually applied as a function transformation using the @wrapper syntax"
[json]: https://www.json.org/ "JSON (JavaScript Object Notation) is a lightweight data-interchange format."
[`pickle`]: https://docs.python.org/library/pickle.html "The pickle module implements binary protocols for serializing and de-serializing a Python object structure."

[bson]: https://bsonspec.org/ "BSON, short for Bin­ary JSON, is a bin­ary-en­coded seri­al­iz­a­tion of JSON-like doc­u­ments."
[msgpack]: https://msgpack.org/ "MessagePack is an efficient binary serialization format."

[uv]: https://docs.astral.sh/uv/ "An extremely fast Python package and project manager, written in Rust."
[pre-commit]: https://pre-commit.com/ "A framework for managing and maintaining multi-language pre-commit hooks."

[`RedisFuncCache`]: redis_func_cache.cache.RedisFuncCache
[`AbstractPolicy`]: redis_func_cache.policies.abstract.AbstractPolicy

[`BaseSinglePolicy`]: redis_func_cache.policies.base.BaseSinglePolicy
[`BaseMultiplePolicy`]: redis_func_cache.policies.base.BaseMultiplePolicy
[`BaseClusterSinglePolicy`]: redis_func_cache.policies.base.BaseClusterSinglePolicy
[`BaseClusterMultiplePolicy`]: redis_func_cache.policies.base.BaseClusterMultiplePolicy

[`FifoPolicy`]: redis_func_cache.policies.fifo.FifoPolicy "First In First Out policy"
[`LfuPolicy`]: redis_func_cache.policies.lfu.LfuPolicy "Least Frequently Used policy"
[`LruPolicy`]: redis_func_cache.policies.lru.LruPolicy "Least Recently Used policy"
[`MruPolicy`]: redis_func_cache.policies.mru.MruPolicy "Most Recently Used policy"
[`RrPolicy`]: redis_func_cache.policies.rr.RrPolicy "Random Remove policy"
[`LruTPolicy`]: redis_func_cache.policies.lru.LruTPolicy "Time based Least Recently Used policy."

[`FifoMultiplePolicy`]: redis_func_cache.policies.fifo.FifoMultiplePolicy
[`LfuMultiplePolicy`]: redis_func_cache.policies.lfu.LfuMultiplePolicy
[`LruMultiplePolicy`]: redis_func_cache.policies.lru.LruMultiplePolicy
[`MruMultiplePolicy`]: redis_func_cache.policies.mru.MruMultiplePolicy
[`RrMultiplePolicy`]: redis_func_cache.policies.rr.RrMultiplePolicy
[`LruTMultiplePolicy`]: redis_func_cache.policies.lru.LruTMultiplePolicy

[`FifoClusterPolicy`]: redis_func_cache.policies.fifo.FifoClusterPolicy
[`LfuClusterPolicy`]: redis_func_cache.policies.lfu.LfuClusterPolicy
[`LruClusterPolicy`]: redis_func_cache.policies.lru.LruClusterPolicy
[`MruClusterPolicy`]: redis_func_cache.policies.mru.MruClusterPolicy
[`RrClusterPolicy`]: redis_func_cache.policies.rr.RrClusterPolicy
[`LruTClusterPolicy`]: redis_func_cache.policies.lru.LruTClusterPolicy

[`LruTClusterMultiplePolicy`]: redis_func_cache.policies.lru.LruTClusterMultiplePolicy
