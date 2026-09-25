# Quick Start

This page walks you through your first cached function, from a running Redis server to sync and async usage, and helps you pick an eviction policy.

## Prerequisites

1. A Redis server, e.g. via Docker:

   ```bash
   docker run -it --rm -p 6379:6379 redis:alpine
   ```

1. The library installed in your Python environment:

   ```bash
   pip install redis_func_cache[hiredis]
   ```

## Why a Redis-backed cache?

In-process caches like the standard library's `functools.cache` are private to a single Python process: every worker re-computes and re-stores the same values, and the cache vanishes on restart. This library uses Redis as the backend, so the cache is:

- **Distributed**: all processes and machines behind your application share one cache — a result computed once is visible to every worker.
- **Persistent across restarts**: cached results survive process restarts and deploys (until evicted or expired).
- **Cluster-ready**: dedicated policies keep each cache's two Redis keys in the same hash slot, so the cache works on Redis Cluster out of the box.
- **Atomic and highly available**: every read/write is a single Lua script executed atomically by Redis; running Redis with replication/Sentinel gives you the usual Redis high-availability story for free.

## Basic Usage

```python
from redis import Redis
from redis_func_cache import RedisFuncCache as Cache, LruTPolicy

factory = lambda: Redis.from_url("redis://")
cache = Cache("quickstart", LruTPolicy, maxsize=128, ttl=300, factory=factory)


@cache
def get_exchange_rate(base: str, quote: str) -> float:
    print("fetching from remote API ...")  # only printed on a cache miss
    ...  # call the real API here
    return 7.25


get_exchange_rate("USD", "CNY")  # cache miss: the function executes, the line is printed
get_exchange_rate("USD", "CNY")  # cache hit: served from Redis, nothing is printed
```

We create a [Redis][] client (via a `factory`, recommended for concurrent use), then a [`RedisFuncCache`][] instance with an [`LruTPolicy`][], and decorate `get_exchange_rate` with it.
The first call executes the function and stores its result in Redis; the second call with the same arguments is served from Redis — the function body never runs.

It works almost the same as the standard library's `functools.lru_cache`, except that the cache lives in [Redis][] and is therefore shared by every process and machine connecting to the same Redis.

## Async Functions

To decorate async functions, supply an async [Redis][] client via the `factory` argument — the example is the same shape as the sync one above:

```python
import asyncio

from redis.asyncio import Redis as AsyncRedis
from redis_func_cache import RedisFuncCache as Cache, LruTPolicy

factory = lambda: AsyncRedis.from_url("redis://")
cache = Cache("quickstart-async", LruTPolicy, maxsize=128, ttl=300, factory=factory)


@cache
async def get_exchange_rate(base: str, quote: str) -> float:
    print("fetching from remote API ...")  # only printed on a cache miss
    ...  # await the real API call here
    return 7.25


async def main():
    await get_exchange_rate("USD", "CNY")  # cache miss: the function executes
    await get_exchange_rate("USD", "CNY")  # cache hit: served from Redis


with asyncio.Runner() as runner:
    runner.run(main())
```

> ❗ **Attention:**
>
> - When a [`RedisFuncCache`][] is created with an async [Redis][] client, it can only be used to decorate async functions. These async functions will be decorated with an asynchronous wrapper, and the I/O operations between the [Redis][] client and server will be performed asynchronously.
> - Conversely, a synchronous [`RedisFuncCache`][] can only decorate synchronous functions. These functions will be decorated with a synchronous wrapper, and I/O operations with [Redis][] will be performed synchronously.

## Choosing an Eviction Policy

The library supports multiple cache eviction policies. You can specify a policy when creating the cache:

```python
from redis import Redis
from redis_func_cache import RedisFuncCache, FifoPolicy, LruTPolicy, LfuPolicy, RrPolicy

factory = lambda: Redis.from_url("redis://")

# FIFO (First In, First Out)
fifo_cache = RedisFuncCache("my-fifo-cache", FifoPolicy, factory=factory)

# LFU (Least Frequently Used)
lfu_cache = RedisFuncCache("my-lfu-cache", LfuPolicy, factory=factory)

# Random Replacement
rr_cache = RedisFuncCache("my-rr-cache", RrPolicy, factory=factory)
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
[`Policy`]: redis_func_cache.policies.Policy
[`SingleKeying`]: redis_func_cache.keying.SingleKeying
[`Hasher`]: redis_func_cache.hashing.Hasher

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
