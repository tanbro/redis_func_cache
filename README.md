# redis_func_cache

[![python-package](https://github.com/tanbro/redis_func_cache/actions/workflows/python-package.yml/badge.svg)](https://github.com/tanbro/redis_func_cache/actions/workflows/python-package.yml)
[![codecov](https://codecov.io/gh/tanbro/redis_func_cache/graph/badge.svg?token=BgeXJZdPbJ)](https://codecov.io/gh/tanbro/redis_func_cache)
[![readthedocs](https://readthedocs.org/projects/redis-func-cache/badge/)](https://redis-func-cache.readthedocs.io/)
[![pypi-version](https://img.shields.io/pypi/v/redis_func_cache.svg)](https://pypi.org/project/redis_func_cache/)

> *A Python library that provides decorators for caching function results in Redis, supporting multiple serialization formats and caching strategies, as well as asynchronous operations.*

## Introduction

`redis_func_cache` is a Python library that provides decorators for caching function results in Redis, similar to the caching functionality offered by the standard library. Like the [`functools`](https://docs.python.org/library/functools.html) module, it includes useful decorators such as [`lru_cache`](https://docs.python.org/library/functools.html#functools.lru_cache), which are valuable for implementing memoization.

When you need to cache function return values across multiple processes or machines, [Redis][] can be used as a distributed backend. The purpose of this project is to provide simple and clean decorator functions to use Redis as a cache backend. It implements caches with various eviction/replacement policies such as LRU, FIFO, RR, and LFU. (Refer to [Cache Replacement Policies on Wikipedia](https://wikipedia.org/wiki/Cache_replacement_policies) for more details.)

Here is a simple example:

1. First, start up a Redis server at 127.0.0.1:6379, e.g.:

   ```bash
   docker run -it --rm -p 6379:6379 redis:alpine
   ```

1. Then install the library in your Python environment:

   ```bash
   pip install redis_func_cache
   ```

1. Finally, run the following Python code:

   ```python
   import asyncio
   from time import time
   import redis.asyncio as aioredis
   from redis_func_cache import LruTPolicy, RedisFuncCache as Cache

    # Create a redis connection pool (simple example)
    pool = aioredis.ConnectionPool.from_url("redis://")
    # Preferred: provide a factory for production/concurrent use
    factory = lambda: aioredis.Redis.from_pool(pool)

    # Create an LRU cache. Note: policy must be an instance and we prefer a factory.
    cache = Cache(__name__, LruTPolicy(), factory=factory)

    # Decorate a function to cache its result
    @cache
    async def a_slow_func():
        t = time()
        await asyncio.sleep(10)  # Sleep to simulate a slow operation
        return f"actual duration: {time() - t}"

    with asyncio.Runner() as runner:
        t = time()
        r = runner.run(a_slow_func())
        print(f"duration={time() - t}, {r=}")

        t = time()
        r = runner.run(a_slow_func())
        print(f"duration={time() - t}, {r=}")
   ```

The output should look like:

```
duration=10.117542743682861, r='1755924146.8998647 ... 1755924156.9133286'
duration=0.001995563507080078, r='1755924146.8998647 ... 1755924156.9133286'
```

We can see that the second call to `a_slow_func()` is served from the cache, which is much faster than the first call, and its result is same as the first call.

## Features

- Built on [redis-py][], the official Python client for [Redis][].
- Simple [decorator][] syntax supporting both **`async`** and common functions, **asynchronous** and synchronous I/O.
- Support [Redis][] **cluster**.
- Multiple caching policies: LRU, FIFO, LFU, RR ...
- Serialization formats: JSON, Pickle, MsgPack, YAML, BSON, CBOR ...

## Installation

- Install from PyPI:

    ```bash
    pip install redis_func_cache
    ```

- Install from source:

    ```bash
    git clone https://github.com/tanbro/redis_func_cache.git
    cd redis_func_cache
    pip install .
    ```

- Or install from Github directly:

    ```bash
    pip install git+https://github.com/tanbro/redis_func_cache.git@main
    ```

The library supports [hiredis](https://github.com/redis/hiredis). Installing it can significantly improve performance. It is an optional dependency and can be installed by running: `pip install redis_func_cache[hiredis]`.

If [Pygments](https://pygments.org/) is installed, the library will automatically remove comments and empty lines from Lua scripts evaluated on the [Redis](https://redis.io/) server, which can slightly improve performance. *Pygments* is also an optional dependency and can be installed by running: `pip install redis_func_cache[pygments]`.

## Data structure

The library combines a pair of [Redis][] data structures to manage cache data:

- The first is a sorted set, which stores the hash values of the decorated function calls along with a score for each item.

    When the cache reaches its maximum size, the score is used to determine which item to evict.

- The second is a hash map, which stores the hash values of the function calls and their corresponding return values.

This can be visualized as follows:

![data_structure](images/data_structure.svg)

The main idea of the eviction policy is that the cache keys are stored in a set, and the cache values are stored in a hash map. Eviction is performed by removing the lowest-scoring item from the set, and then deleting the corresponding field and value from the hash map.

Here is an example showing how the *LRU* cache's eviction policy works (maximum size is 3):

![eviction_example](images/eviction_example.svg)

The [`RedisFuncCache`][] executes a decorated function with specified arguments and caches its result. Here's a breakdown of the steps:

1. **Initialize Scripts**: Retrieve two Lua script objects for cache hit and update from `policy.lua_scripts`.
1. **Calculate Keys and Hash**: Compute the cache keys using `policy.calc_keys`, compute the hash value using `policy.calc_hash`, and compute any additional arguments using `policy.calc_ext_args`.
1. **Attempt Cache Retrieval**: Attempt to retrieve a cached result. If a cache hit occurs, deserialize and return the cached result.
1. **Execute User Function**: If no cache hit occurs, execute the decorated function with the provided arguments and keyword arguments.
1. **Serialize Result and Cache**: Serialize the result of the user function and store it in Redis.
1. **Return Result**: Return the result of the decorated function.

```mermaid
flowchart TD
    A[Start] --> B[Initialize Scripts]
    B --> C{Scripts Valid?}
    C -->|Invalid| D[Raise RuntimeError]
    C -->|Valid| E[Calculate Keys and Hash]
    E --> F[Attempt Cache Retrieval]
    F --> G{Cache Hit?}
    G -->|Yes| H[Deserialize and Return Cached Result]
    G -->|No| I[Execute User Function]
    I --> J[Serialize Result]
    J --> K[Store in Cache]
    K --> L[Return User Function Result]
```

## Concurrency and atomicity

The library guarantees thread safety and concurrency security through the following design principles:

1. Redis Concurrency

   - The underlying redis-py client is not thread-safe. Each thread should use a separate client instance or a connection pool (`redis.ConnectionPool`) which is advised to avoid resource contention.
   - It is recommended to use a **factory and pool** pattern for client instantiation, preventing race conditions during connection creation. A pre-configured connection pool helps manage Redis connections efficiently and prevents exhaustion under high concurrency.
   - All Redis operations (e.g., get, put) are executed via Lua scripts to ensure atomicity, preventing race conditions during concurrent access.

   Here is an example using `redis.ConnectionPool` to avoid conflicts when the cache accesses Redis:

   ```python
   import redis
   from redis_func_cache import RedisFuncCache, LruPolicy

   redis_pool = redis.ConnectionPool(...)  # Use a pool, not a single client
   factory = lambda: redis.from_pool(redis_pool)  # Use factory, not a static client

   cache = RedisFuncCache(__name__, LruPolicy(), factory=factory)

   @cache
   def your_concurrent_func(...):
       ...
   ```

1. Function Execution Concurrency

   Both synchronous and asynchronous functions decorated by RedisFuncCache are executed as-is. Therefore, each function is responsible for its own thread, coroutine or process safety.
   The only concurrency risk lies in Redis I/O and operations. The cache will use a synchronous Redis client for synchronous functions and an asynchronous Redis client for asynchronous functions.
   As described above, you should provide an appropriate Redis client or factory to the cache in concurrent scenarios.

1. Contextual State Isolation

   The [ContextVar](https://docs.python.org/3/library/contextvars.html#contextvars.ContextVar) based `mode_context()` context manager and other cache control context managers ensure thread and coroutine isolation. Each thread or async task maintains its own independent state, preventing cross-context interference.

Atomicity is a key feature of this library. All cache operations (both read and write) are implemented using Redis Lua scripts, which are executed atomically by the Redis server. This means that each script runs in its entirety without being interrupted by other operations, ensuring data consistency even under high concurrent load.

Each cache policy implements two Lua scripts:

- A "get" script that attempts to retrieve a value from cache and updates access information
- A "put" script that adds or updates a value in cache and performs eviction if necessary

These scripts operate on the cache data structures (a sorted set for tracking items and a hash map for storing values) in a single atomic operation. This prevents race conditions that could occur if multiple Redis commands were issued separately.

For Redis Cluster deployments, it's important to note that atomicity is guaranteed only within a single key's hash slot. Since our implementation uses two keys (a sorted set and a hash map) for each cache instance, both keys are designed to belong to the same hash slot. The cluster policies automatically calculate key slots to ensure that all cache data for a single cache instance is always located on the same node in the cluster. This design guarantees that cache operations can be executed atomically within the cluster environment.

These designs enable safe operation in both multi-threaded and asynchronous environments while maintaining high-performance Redis I/O throughput. For best results, use the library with Redis 6.0 or newer to take advantage of native Lua script atomicity and advanced connection management features.

## Important Considerations

Before using this library, please be aware of the following important considerations:

### Cache Stampede Risk

> ⚠️ **Important:** \
> When a cached function is expensive and called concurrently with the same arguments, multiple calls may execute simultaneously if the cache is empty or expired. This is known as **"cache stampede"** or **"thundering herd"** problem.

#### Understanding the Problem

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

#### Mitigation Strategies

Since this is fundamentally an **application-level concern**, the mitigation strategy should be chosen and implemented by you based on your requirements:

##### Strategy 1: Redis Distributed Lock (Recommended for Distributed Systems)

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

##### Strategy 2: Semaphore (For Single-Process Concurrency)

For single-process scenarios, use Python's threading primitive:

```python
from threading import Semaphore
from redis_func_cache import RedisFuncCache, LruTPolicy

cache = RedisFuncCache("my-cache", LruTPolicy(), client=redis_client)

# Limit concurrent executions to 1
semaphore = Semaphore(1)

@cache
def expensive_function(x: int) -> int:
    with semaphore:
        # Only one thread can execute this block at a time
        return x * x  # Your expensive operation
```

##### Strategy 3: TTL Jitter

Add random jitter to cache expiration to prevent simultaneous expirations:

```python
import random
from redis_func_cache import RedisFuncCache, LruTPolicy

# Base TTL + random jitter (0-60 seconds)
cache = RedisFuncCache(
    "my-cache",
    LruTPolicy(),
    client=redis_client,
    ttl=300 + random.randint(0, 60)
)
```

##### Strategy 4: Stale-While-Revalidate (Advanced)

Allow returning slightly stale data while refreshing the cache in the background. This requires custom implementation outside the library's core functionality.

#### Choosing the Right Strategy

| Strategy               | Best For                                     | Trade-offs                                 |
| ---------------------- | -------------------------------------------- | ------------------------------------------ |
| Redis Lock             | Distributed systems, long-running functions  | Adds latency for waiting threads           |
| Semaphore              | Single-process scenarios                     | Not suitable for multi-process deployments |
| TTL Jitter             | Preventing mass expiration                   | Doesn't prevent stampede on cold cache     |
| Stale-While-Revalidate | Read-heavy workloads, tolerant of stale data | Requires complex implementation            |

> 💡 **Recommendation:** Start with **Strategy 1 (Redis Lock)** for most distributed applications. It provides the best balance between correctness and usability.

For more detailed examples and advanced patterns, see [Important Considerations - Cache Stampede Risk](#important-considerations).

### Other Key Limitations

- **Generator functions** are not supported.
- **Decorator compatibility** with other decorators is not guaranteed.
- **Unique cache names**: Each [`RedisFuncCache`][] instance must have a unique `name` argument. Sharing the same name across different instances may lead to serious errors.

## Getting Started

### Basic Usage

Using an *LRU* cache to decorate a recursive Fibonacci function:

> 💡 **Tip**: \
> `RedisFuncCache` is not effective for recursive functions, use standard library's `functools.lru_cache` for production instead.

```python
from redis import Redis
from redis_func_cache import RedisFuncCache as Cache, LruTPolicy

factory = lambda: Redis("redis://")

lru_cache = Cache("my-first-lru-cache", LruTPolicy(), factory)

@lru_cache
def fib(n):
    if n <= 1:
        return n
    if n == 2:
        return 1
    return fib(n - 1) + fib(n - 2)
```

In this example, we first create a [Redis][] client, then create a [`RedisFuncCache`][] instance with the [Redis][] client and [`LruTPolicy`][] as its arguments.
Next, we use the `@lru_cache` [decorator][] to decorate the `fib` function.
This way, each computed result is cached, and subsequent calls with the same parameters retrieve the result directly from the cache, thereby improving performance.

It works almost the same as the standard library's `functools.lru_cache`, except that it uses [Redis][] as the backend instead of the local machine's memory.

### Async Functions

To decorate async functions, you should pass an `Async Redis client` to [`RedisFuncCache`][]'s `client` argument:

```python
from redis.asyncio import Redis as AsyncRedis
from redis_func_cache import RedisFuncCache as Cache, LruTPolicy

factory = lambda: AsyncRedis.from_url("redis://")
cache = Cache(__name__, LruTPolicy(), factory)

@cache
async def my_async_func(...):
    ...
```

> ❗ **Attention:**
>
> - When a [`RedisFuncCache`][] is created with an async [Redis][] client, it can only be used to decorate async functions. These async functions will be decorated with an asynchronous wrapper, and the I/O operations between the [Redis][] client and server will be performed asynchronously.
> - Conversely, a synchronous [`RedisFuncCache`][] can only decorate synchronous functions. These functions will be decorated with a synchronous wrapper, and I/O operations with [Redis][] will be performed synchronously.

### Choosing an Eviction Policy

The library supports multiple cache eviction policies. You can specify a policy when creating the cache:

```python
from redis import Redis
from redis_func_cache import RedisFuncCache, FifoPolicy, LruTPolicy, LfuPolicy, RrPolicy

redis_client = Redis.from_url("redis://")

# FIFO (First In, First Out)
fifo_cache = RedisFuncCache("my-fifo-cache", FifoPolicy(), client=redis_client)

# LFU (Least Frequently Used)
lfu_cache = RedisFuncCache("my-lfu-cache", LfuPolicy(), client=redis_client)

# Random Replacement
rr_cache = RedisFuncCache("my-rr-cache", RrPolicy(), client=redis_client)
```

Available policies:

- **[`LruTPolicy`][]** (Recommended): Time-based LRU, offers the best balance of performance and accuracy for most use cases.
- [`FifoPolicy`][]: First in, first out
- [`LfuPolicy`][]: Least frequently used
- [`LruPolicy`][]: Least recently used (more precise but slower than LRU-T)
- [`MruPolicy`][]: Most recently used
- [`RrPolicy`][]: Random remove

> ℹ️ **Info:**\
> Explore the source code in the directory `src/redis_func_cache/policies` for more details.

## Configuration

### Cache Size and TTL

Control cache size and expiration:

```python
cache = RedisFuncCache(
    "my-cache",
    LruTPolicy(),
    client=redis_client,
    maxsize=100,      # Maximum number of cached items
    ttl=300          # Cache expires after 300 seconds of inactivity
)
```

- **`maxsize`**: Maximum number of items the cache can hold. When reached, items are evicted according to the policy.
- **`ttl`**: Time-to-live in seconds. The entire cache structure expires after this period of inactivity (sliding expiration).

For "multiple" policies, each decorated function has its own independent data structure, so `maxsize` and `ttl` apply to each function's cache individually.

#### Per-Item TTL (Experimental)

You can also set TTL on individual cached items:

```python
@cache(ttl=300)  # Each result expires after 300 seconds
def my_func(x):
    ...
```

> ⚠️ **Warning:** This feature requires [Redis][] 7.4+ and uses [Redis Hashes Field expiration](https://redis.io/docs/latest/develop/data-types/hashes/#field-expiration). When a field expires, it's removed from the HASH but the corresponding entry in the ZSET is only lazily cleaned up.

### Serialization

The default serializer is [JSON][], which works with simple data types. For complex objects, you can specify alternative serializers:

```python
import pickle
from redis_func_cache import RedisFuncCache, LruTPolicy

# Method 1: Set at cache instance level
cache = RedisFuncCache(
    __name__,
    LruTPolicy(),
    factory=lambda: Redis.from_url("redis://"),
    serializer="pickle"  # or (pickle.dumps, pickle.loads)
)

# Method 2: Override at decorator level
@cache(serializer="pickle")
def my_func_with_complex_return(x):
    return {...}  # Complex object
```

Supported serializers: JSON, Pickle, MsgPack, YAML, BSON, CBOR, and cloudpickle.

> ⚠️ **Warning:** [`pickle`][] can execute arbitrary code during deserialization. Use with extreme caution, especially with untrusted data.

### Handling Non-Serializable Arguments

For functions with non-serializable arguments (e.g., database connections), use `excludes` or `excludes_positional`:

```python
@cache(excludes=["session", "config"])
def get_user_data(session, user_id: int, config=None):
    # session and config are excluded from cache key
    return fetch_user_data(user_id)

# These calls hit the same cache entry
data1 = get_user_data(session1, user_id=123, config=config1)
data2 = get_user_data(session2, user_id=123, config=config2)  # Cache hit
```

### Multiple Key Pairs

By default, all decorated functions share the same Redis key pair. To give each function its own keys, use a "Multiple" policy:

```python
from redis_func_cache import RedisFuncCache, LruTMultiplePolicy

cache = RedisFuncCache("my-cache", LruTMultiplePolicy(), client=redis_client)

@cache
def func1(x):
    ...

@cache
def func2(x):
    ...

# func1 and func2 have separate Redis key pairs
```

Available multiple-key policies: [`FifoMultiplePolicy`][], [`LfuMultiplePolicy`][], [`LruMultiplePolicy`][], [`LruTMultiplePolicy`][], [`MruMultiplePolicy`][], [`RrMultiplePolicy`][].

### Redis Cluster

For Redis Cluster deployments, use a Cluster-aware policy. These policies use hash tags `{...}` to ensure both keys are on the same cluster node:

```python
from redis_func_cache import RedisFuncCache, LruTClusterPolicy

cache = RedisFuncCache("my-cache", LruTClusterPolicy(), client=redis_client)

@cache
def my_func(x):
    ...
```

Available cluster policies: [`FifoClusterPolicy`][], [`LfuClusterPolicy`][], [`LruClusterPolicy`][], [`LruTClusterPolicy`][], [`MruClusterPolicy`][], [`RrClusterPolicy`][].

For per-function keys in cluster mode, use `*ClusterMultiplePolicy` variants: [`LruTClusterMultiplePolicy`][], etc.

### Cache Mode Control

Fine-grained control over cache behavior:

```python
from redis_func_cache import RedisFuncCache

@cache
def get_user_data(user_id):
    return data

# Normal operation
data = get_user_data(123)

# Bypass cache reading, but still write to cache
with cache.write_only():
    data = get_user_data(123)  # Function executed, result cached

# Only read from cache
with cache.read_only():
    data = get_user_data(123)  # Only attempts to read from cache

# Disable cache entirely
with cache.disable_rw():
    data = get_user_data(123)  # Function executed, no cache interaction
```

## Migration Guide (v0.6 → v0.7)

v0.7 introduced breaking changes to the `RedisFuncCache` constructor:

### Summary of Changes

- The Redis client parameters renamed to `client` and `factory`. `factory` is preferred for concurrent/production use.
- The `policy` parameter must now be an **instance** (e.g., `LruTPolicy()`), not a class.
- Passing a callable as the `client` positional argument is deprecated. Use `factory=` instead.

### Migration Example

**Old (pre-v0.7.0):**

```python
import redis
from redis_func_cache import RedisFuncCache, LruTPolicy

pool = redis.ConnectionPool.from_url("redis://")
factory = lambda: redis.Redis.from_pool(pool)
# Passing policy class and client positional arg
cache = RedisFuncCache("my-cache", LruTPolicy, client=factory)
```

**New (v0.7.0+):**

```python
import redis
from redis_func_cache import RedisFuncCache, LruTPolicy

pool = redis.ConnectionPool.from_url("redis://")
factory = lambda: redis.Redis.from_pool(pool)
# Policy must be instantiated; use factory= keyword
cache = RedisFuncCache("my-cache", LruTPolicy(), factory=factory)
```

## Advanced Usage

### Custom Serializer

The result of the decorated function is serialized by default using [JSON][] (via the json module from the standard library) and then saved to [Redis][].

To utilize alternative serialization methods, such as [msgpack][], you have two options:

1. Specify the `serializer` argument in the constructor of [`RedisFuncCache`][], where the argument is a tuple of `(serializer, deserializer)`, or the name of the serializer function:

   This method applies globally: all functions decorated by this cache will use the specified serializer.

   For example:

   ```python
   import bson
   from redis import Redis
   from redis_func_cache import RedisFuncCache, LruTPolicy

   def serialize(x):
      return bson.encode({"return_value": x})

   def deserialize(x):
      return bson.decode(x)["return_value"]

   cache = RedisFuncCache(
       __name__,
       LruTPolicy(),
       factory=lambda: Redis.from_url("redis://"),
       serializer=(serialize, deserialize)
    )

   @cache
   def func():
      ...
   ```

1. Specify the `serializer` argument directly in the decorator. The argument should be a tuple of (`serializer`, `deserializer`) or simply the name of the serializer function.

   This method applies on a per-function basis: only the decorated function will use the specified serializer.

   For example:

   - We can use [msgpack][] as the serializer to cache functions whose return value is binary data, which is not possible with [JSON][].
   - We can use [bson][] as the serializer to cache functions whose return value is a `datetime` object, which cannot be handled by either [JSON][] or [msgpack][].

   ```python
   import msgpack
   from redis import Redis
   from redis_func_cache import RedisFuncCache, LruTPolicy

   cache = RedisFuncCache(__name__, LruTPolicy(), factory=lambda: Redis.from_url("redis://"))

   @cache(serializer=(msgpack.packb, msgpack.unpackb))
   def create_or_get_token(user: str) -> bytes:
      from secrets import token_bytes
      return token_bytes(32)

   @cache(serializer="bson")
   def now_time():
       from datetime import datetime
       return datetime.now()
   ```

### Custom key format

An instance of [`RedisFuncCache`][] calculates key pair names by calling the `calc_keys` method of its policy.
There are four basic policies that implement respective kinds of key formats:

- [`BaseSinglePolicy`][]: All functions share the same key pair, [Redis][] cluster is NOT supported.

    The format is: `<prefix><name>:<__key__>:<0|1>`

- [`BaseMultiplePolicy`][]: Each function has its own key pair, [Redis][] cluster is NOT supported.

    The format is: `<prefix><name>:<__key__>:<function_name>#<function_hash>:<0|1>`

- [`BaseClusterSinglePolicy`][]: All functions share the same key pair, [Redis][] cluster is supported.

    The format is: `<prefix>{<name>:<__key__>}:<0|1>`

- [`BaseClusterMultiplePolicy`][]: Each function has its own key pair, and [Redis][] cluster is supported.

    The format is: `<prefix><name>:<__key__>:<function_name>#{<function_hash>}:<0|1>`

Variables in the format string are defined as follows:

|                 |                                                                      |
| --------------- | -------------------------------------------------------------------- |
| `prefix`        | `prefix` argument of [`RedisFuncCache`][]                            |
| `name`          | `name` argument of [`RedisFuncCache`][]                              |
| `__key__`       | `__key__` attribute of the policy class used in [`RedisFuncCache`][] |
| `function_name` | full name of the decorated function                                  |
| `function_hash` | hash value of the decorated function                                 |

`0` and `1` at the end of the keys are used to distinguish between the two data structures:

- `0`: a sorted or unsorted set, used to store the hash value and sorting score of function invocations
- `1`: a hash table, used to store the return value of the function invocation

If you want to use a different format, you can subclass [`AbstractPolicy`][] or any of the above policy classes, and implement the `calc_keys` method, then pass the custom policy class to [`RedisFuncCache`][].

The following example demonstrates how to customize the key format for an *LRU* policy:

```python
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Mapping, Sequence, Tuple, override

import redis
from redis_func_cache import RedisFuncCache
from redis_func_cache.policies.abstract import AbstractPolicy
from redis_func_cache.mixins.hash import PickleMd5HashMixin
from redis_func_cache.mixins.scripts import LruScriptsMixin

if TYPE_CHECKING:
    from redis.typing import KeyT


def factory():
    return redis.from_url("redis://")


MY_PREFIX = "my_prefix"


class MyPolicy(LruScriptsMixin, PickleMd5HashMixin, AbstractPolicy):
    __key__ = "my_key"

    @override
    def calc_keys(
            self, f: Callable | None = None, args: Sequence | None = None, kwds: Mapping[str, Any] | None = None
    ) -> Tuple[KeyT, KeyT]:
        k = f"{self.cache.prefix}-{self.cache.name}-{f.__name__}-{self.__key__}"
        return f"{k}-set", f"{k}-map"


my_cache = RedisFuncCache(name="my_cache", policy=MyPolicy(), factory=factory, prefix=MY_PREFIX)


@my_cache
def my_func(*args, **kwargs):
    ...
```

In the example, we'll get a cache that generates [Redis][] keys separated by `-`, instead of `:`, prefixed by `"my-prefix"`, and suffixed by `"set"` and `"map"`, rather than `"0"` and `"1"`. The key pair names could be like `my_prefix-my_cache_func-my_key-set` and `my_prefix-my_cache_func-my_key-map`.

`LruScriptsMixin` tells the policy which Lua script to use, and `PickleMd5HashMixin` tells the policy to use [`pickle`][] to serialize and `md5` to calculate the hash value of the function.

> ❗ **Important:**\
> The calculated key name **SHOULD** be unique for each [`RedisFuncCache`][] instance.
>
> [`BaseSinglePolicy`][], [`BaseMultiplePolicy`][], [`BaseClusterSinglePolicy`][], and [`BaseClusterMultiplePolicy`][] calculate their key names by calling the `calc_keys` method, which uses their `__key__` attribute and the `name` property of the [`RedisFuncCache`][] instance.
> If you subclass any of these classes, you should override the `__key__` attribute to ensure that the key names remain unique.

### Custom Hash Algorithm

When the library performs a get or put action with [Redis][], the hash value of the function invocation will be used.

For the sorted set data structures, the hash value will be used as the member. For the hash map data structure, the hash value will be used as the hash field.

The algorithm used to calculate the hash value is defined in `AbstractHashMixin`, and can be described as below:

```python
import hashlib

class AbstractHashMixin:
    __hash_config__ = ...

    ...

    def calc_hash(self, f = None, args = None, kwds = None):
        if not callable(f):
            raise TypeError(f"Cannot calculate hash for {f=}")
        conf = self.__hash_config__
        h = hashlib.new(conf.algorithm)
        h.update(f"{f.__module__}:{f.__qualname__}".encode())
        h.update(f.__code__.co_code)
        if args is not None:
            h.update(conf.serializer(args))
        if kwds is not None:
            h.update(conf.serializer(kwds))
        if conf.decoder is None:
            return h.digest()
        return conf.decoder(h)
```

As the code snippet above shows, the hash value is calculated by the full name of the function, the bytecode of the function, and the arguments and keyword arguments — they are serialized and hashed, then decoded.

The serializer and decoder are defined in the `__hash_config__` attribute of the policy class and are used to serialize arguments and decode the resulting hash. By default, the serializer is [`pickle`][] and the decoder uses the md5 algorithm. If no decoder is specified, the hash value is returned as bytes.

This configuration can be illustrated as follows:

```mermaid
flowchart TD
    A[Start] --> B{Is f callable?}
    B -->|No| C[Throw TypeError]
    B -->|Yes| D[Get config conf]
    D --> E[Create hash object h]
    E --> F[Update hash: module name and qualified name]
    F --> G[Update hash: function bytecode]
    G --> H{Are args not None?}
    H -->|Yes| I[Update hash: serialize args]
    H -->|No| J{Are kwds not None?}
    I --> J
    J -->|Yes| K[Update hash: serialize kwds]
    J -->|No| L{Is conf.decoder None?}
    K --> L
    L -->|Yes| M[Return digest bytes]
    L -->|No| N[Return decoded digest]
```

If we want to use a different algorithm, we can select a mixin hash class defined in `src/redis_func_cache/mixins/hash.py`. For example:

- To serialize the function with [JSON][], use the SHA1 hash algorithm, store hex string in redis, you can choose the `JsonSha1HexHashMixin` class.
- To serialize the function with [`pickle`][], use the MD5 hash algorithm, store base64 string in redis, you can choose the `PickleMd5Base64HashMixin` class.

These mixin classes provide alternative hash algorithms and serializers, allowing for flexible customization of the hashing behavior. The following example shows how to use the `JsonSha1HexHashMixin` class:

```python
from redis import Redis
from redis_func_cache import RedisFuncCache
from redis_func_cache.policies.abstract import AbstractPolicy
from redis_func_cache.mixins.hash import JsonSha1HexHashMixin
from redis_func_cache.mixins.scripts import LruScriptsMixin


class MyLruPolicy(LruScriptsMixin, JsonSha1HexHashMixin, AbstractPolicy):
    __key__ = "my-lru"

my_json_sha1_hex_cache = RedisFuncCache(
    name="json_sha1_hex",
    policy=MyLruPolicy(),
    factory=lambda: Redis.from_url("redis://")
)
```

Or even write an entire new algorithm. For that, we subclass `AbstractHashMixin` and override the `calc_hash` method. For example:

```python
from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, override, Any, Callable, Mapping, Sequence
import cloudpickle
from redis import Redis
from redis_func_cache import RedisFuncCache
from redis_func_cache.policies.abstract import AbstractPolicy
from redis_func_cache.mixins.hash import AbstractHashMixin
from redis_func_cache.mixins.scripts import LruScriptsMixin

if TYPE_CHECKING:  # pragma: no cover
    from redis.typing import KeyT


class MyHashMixin(AbstractHashMixin):
    @override
    def calc_hash(
        self,
        f: Callable | None = None,
        args: Sequence | None = None,
        kwds: Mapping[str, Any] | None = None
    ) -> KeyT:
        assert callable(f)
        dig = hashlib('balck2b')
        dig.update(f.__qualname__.encode())
        dig.update(cloudpickle.dumps(args))
        dig.update(cloudpickle.dumps(kwds))
        return dig.hexdigest()


class MyLruPolicy2(LruScriptsMixin, MyHashMixin, AbstractPolicy):
    __key__ = "my-lru2"


my_custom_hash_cache = RedisFuncCache(
    name=__name__,
    policy=MyLruPolicy2(),
    client=redis_client
)

redis_client = Redis.from_url("redis://")


@my_custom_hash_cache
def some_func(*args, **kwargs):
    ...
```

> 💡 **Tip:**\
> The purpose of the hash algorithm is to ensure the isolation of cached return values for different function invocations.
> Therefore, you can generate unique key names using any method, not just hashes.

## Known Issues

- Cannot decorate a function that has an argument not serializable by [`pickle`][] or other serialization libraries.

  - For a common method defined inside a class, the class must be serializable; otherwise, the first `self` argument cannot be serialized.
  - For a class method (decorated by [`@classmethod`](https://docs.python.org/3/library/functions.html#classmethod)), the class type itself, i.e., the first `cls` argument, must be serializable.

  Anyhow, we can work around this issue by excluding the unsupported arguments from the key and hash calculations with `excludes` and/or `excludes_positional` parameters.

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

  cache = Cache(__name__, policy=MyLfuPolicy, client=redis_client_factory)
  ```

  As shown above, the `JsonMd5HashMixin` uses [json][], which can be used across different Python versions, rather than [`pickle`][]. `use_bytecode` is set to `False` to avoid version compatible problems caused by bytecode.

- The cache eviction policies are mainly based on [Redis][] sorted set's score ordering. For most policies, the score is a positive integer. Its maximum value is `2^32-1` in [Redis][], which limits the number of times of eviction replacement. [Redis][] will return an `overflow` error when the score overflows.

- **Cache Stampede Risk:** Under high concurrency, multiple requests with identical arguments may simultaneously execute the decorated function when the cache is empty or expired. This is a **known limitation** by design—concurrency control is the responsibility of the application layer. See [Important Considerations - Cache Stampede Risk](#important-considerations) for mitigation strategies and code examples.

- Generator functions are not supported.

- If there are multiple [`RedisFuncCache`][] instances with the same name, they may share the same cache data.
  This may lead to serious errors, so we should avoid using the same `name` argument for different cache instances.

- The Redis keys generated by *Multiple* policies include a hash derived from Python bytecode, making them **incompatible across Python versions**.

  However, you can define a custom mixin that inherits from `AbstractHashMixin`, in which you can implement your own hash function to support compatibility across Python versions.

  Additionally, the decorator **cannot be used with native or built-in functions** due to same limitation.

## Test

1. Start a Redis server
1. Set up `REDIS_URL` environment variable (Default to `redis://` if not defined) to point to the Redis server.
1. Run the tests:

   ```bash
   python -m unittest
   ```

A Docker Compose file for unit testing is provided in the `docker` directory to simplify the process. You can run it by executing:

```bash
cd docker
docker compose up --abort-on-container-exit
```

## Develop

Clone the project and enter the project directory:

```bash
git clone https://github.com/tanbro/redis_func_cache.git
cd redis_func_cache
```

We can use either the traditional method (`venv` and `pip`) of standard library or [uv][] as the environment manager.

- If using the traditional method, a virtual environment is recommended:

  1. Install a Python development environment on your system. The minimum required Python version is 3.9.

  1. Initialize a virtual environment at sub-directory `.venv`, then activate it:

     - On Unix-like systems:

        ```bash
        python -m venv .venv
        source .venv/bin/activate
        ```

        > 💡 **Tip:** \
        > On some older systems, `python` may be a symbolic link to `python2`. In such cases, you can use `python3` instead.

     - On Windows:

        ```powershell
        python -m venv .venv
        .venv\Scripts\Activate
        ```

        > 💡 **Tip:** \
        > On Windows, the command-line executable for Python may be either `python`, `python3` or `py`, depending on your installation method.

  1. Install the project with all extras and its development group dependencies:

     ```bash
     pip install -e[all] . --group dev
     ```

- If using [uv][], just the project with all extras and its development group dependencies:

  ```bash
  uv sync --all-groups --dev
  ```

  A Python virtual environment is created in the `.venv` directory by [uv][] automatically.

We suggest installing [pre-commit][] hooks:

```bash
pre-commit install
```

> ℹ️ **Note:** \
> Ensure that you have a stable internet connection during the installation process to avoid interruptions.

### Module structure

```mermaid
graph LR
    RedisFuncCache --> AbstractPolicy
    RedisFuncCache --> Serializer
    RedisFuncCache --> ScriptExecution
    AbstractPolicy --> BaseSinglePolicy
    AbstractPolicy --> BaseMultiplePolicy
    AbstractPolicy --> BaseClusterSinglePolicy
    AbstractPolicy --> BaseClusterMultiplePolicy
    BaseSinglePolicy --> FifoPolicy
    BaseSinglePolicy --> LfuPolicy
    BaseSinglePolicy --> LruPolicy
    BaseSinglePolicy --> MruPolicy
    BaseSinglePolicy --> RrPolicy
    BaseSinglePolicy --> LruTPolicy
    BaseMultiplePolicy --> FifoMultiplePolicy
    BaseMultiplePolicy --> LfuMultiplePolicy
    BaseMultiplePolicy --> LruMultiplePolicy
    BaseMultiplePolicy --> MruMultiplePolicy
    BaseMultiplePolicy --> RrMultiplePolicy
    BaseMultiplePolicy --> LruTMultiplePolicy
    BaseClusterSinglePolicy --> FifoClusterPolicy
    BaseClusterSinglePolicy --> LfuClusterPolicy
    BaseClusterSinglePolicy --> LruClusterPolicy
    BaseClusterSinglePolicy --> MruClusterPolicy
    BaseClusterSinglePolicy --> RrClusterPolicy
    BaseClusterSinglePolicy --> LruTClusterPolicy
    BaseClusterMultiplePolicy --> FifoClusterMultiplePolicy
    BaseClusterMultiplePolicy --> LfuClusterMultiplePolicy
    BaseClusterMultiplePolicy --> LruClusterMultiplePolicy
    BaseClusterMultiplePolicy --> MruClusterMultiplePolicy
    BaseClusterMultiplePolicy --> RrClusterMultiplePolicy
    BaseClusterMultiplePolicy --> LruTClusterMultiplePolicy
    FifoPolicy --> FifoScriptsMixin
    LfuPolicy --> LfuScriptsMixin
    LruPolicy --> LruScriptsMixin
    MruPolicy --> MruScriptsMixin
    RrPolicy --> RrScriptsMixin
    LruTPolicy --> LruTScriptsMixin
    FifoScriptsMixin --> fifo_get.lua
    FifoScriptsMixin --> fifo_put.lua
    LruScriptsMixin --> lru_get.lua
    LruScriptsMixin --> lru_put.lua
    LruTScriptsMixin --> lru_t_get.lua
    LruTScriptsMixin --> lru_t_put.lua
    Serializer --> json
    Serializer --> pickle
    Serializer --> msgpack
    Serializer --> bson
    Serializer --> yaml
    Serializer --> cbor
    Serializer --> cloudpickle
    ScriptExecution --> redis.commands.core.Script
    ScriptExecution --> redis.commands.core.AsyncScript
    RedisFuncCache --> utils.py
    utils.py --> b64digest
    utils.py --> get_callable_bytecode
```

### Class Diagrams

Core class:

```mermaid
classDiagram
    class RedisFuncCache {
        -client: RedisClientTV
        -policy: AbstractPolicy
        -serializer: SerializerPairT
        +__init__(name, policy, client, serializer)
        +__call__(func)
        +decorate(func)
        +exec(user_function, user_args, user_kwds)
        +aexec(user_function, user_args, user_kwds)
    }

    class AbstractPolicy {
        <<abstract>>
        __key__: str
        __scripts__: Tuple[str, str]
        +__init__(cache)
        +calc_keys(f, args, kwds) -> Tuple[str, str]
        +calc_hash(f, args, kwds) -> KeyT
        +purge() -> int
        +apurge() -> int
    }

    class BaseSinglePolicy {
        _keys: Optional[Tuple[str, str]]
        +__init__(cache)
        +calc_keys(f, args, kwds) -> Tuple[str, str]
        +purge()
        +apurge()
    }

    class BaseMultiplePolicy {
        +calc_keys(f, args, kwds) -> Tuple[str, str]
    }

    RedisFuncCache --> AbstractPolicy : uses
    AbstractPolicy <|-- BaseSinglePolicy
    AbstractPolicy <|-- BaseMultiplePolicy
```

Strategy pattern and mixins:

```mermaid
classDiagram
    class LruPolicy {
        __key__ = "lru"
    }

    class LruScriptsMixin {
        __scripts__ = "lru_get.lua", "lru_put.lua"
    }

    class PickleMd5HashMixin {
        __hash_config__ = ...
    }

    BaseSinglePolicy <|-- LruPolicy
    LruScriptsMixin -- LruPolicy
    PickleMd5HashMixin -- LruPolicy

    class FifoPolicy {
        __key__ = "fifo"
    }

    class FifoScriptsMixin {
        __scripts__ = "fifo_get.lua", "fifo_put.lua"
    }

    BaseSinglePolicy <|-- FifoPolicy
    FifoScriptsMixin -- FifoPolicy
    PickleMd5HashMixin -- FifoPolicy
```

Cluster and multiple-keys support

```mermaid
classDiagram
    class BaseClusterSinglePolicy {
        +calc_keys(f, args, kwds) -> Tuple[str, str]
    }

    class BaseClusterMultiplePolicy {
        +calc_keys(f, args, kwds) -> Tuple[str, str]
    }

    BaseSinglePolicy <|-- BaseClusterSinglePolicy
    BaseMultiplePolicy <|-- BaseClusterMultiplePolicy

    class LruClusterPolicy {
        __key__ = "lru-cluster"
    }

    BaseClusterSinglePolicy <|-- LruClusterPolicy
```

Decorator and proxy:

```mermaid
classDiagram
    class RedisFuncCache {
        +__call__(user_function) -> CallableTV
        +decorate(user_function) -> CallableTV
    }

    class Wrapper {
        +wrapper(*user_args, **user_kwargs)
        +awrapper(*user_args, **user_kwargs)
    }

    RedisFuncCache --> Wrapper
```

Weak reference:

```mermaid
classDiagram
    class AbstractPolicy {
        -_cache: CallableProxyType[RedisFuncCache]
        +cache: RedisFuncCache
    }

    class RedisFuncCache {
        -_policy_instance: AbstractPolicy
    }

    RedisFuncCache --> AbstractPolicy : creates
    AbstractPolicy --> CallableProxyType : weak reference
```

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
