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
from redis_func_cache import RedisFuncCache as Cache

pool = Redis.ConnectionPool.from_url("redis://")
factory = lambda: Redis.from_pool(pool)
cache = Cache("quickstart", maxsize=128, ttl=300, factory=factory)


@cache
def get_exchange_rate(base: str, quote: str) -> float:
    print("fetching from remote API ...")  # only printed on a cache miss
    ...  # call the real API here
    return 7.25


get_exchange_rate("USD", "CNY")  # cache miss: the function executes, the line is printed
get_exchange_rate("USD", "CNY")  # cache hit: served from Redis, nothing is printed
```

We create a [Redis][] client (via a `factory`, recommended for concurrent use), then a [`RedisFuncCache`][] instance — no `policy` argument, so it uses the default [`lru_t_policy`][] (time-based LRU) — and decorate `get_exchange_rate` with it.
The first call executes the function and stores its result in Redis; the second call with the same arguments is served from Redis — the function body never runs.

It works almost the same as the standard library's `functools.lru_cache`, except that the cache lives in [Redis][] and is therefore shared by every process and machine connecting to the same Redis.

## Async Functions

To decorate async functions, supply an async [Redis][] client via the `factory` argument — the example is the same shape as the sync one above:

```python
import asyncio

from redis.asyncio import Redis as AsyncRedis
from redis_func_cache import RedisFuncCache as Cache

pool = AsyncRedis.ConnectionPool.from_url("redis://")
factory = lambda: AsyncRedis.from_pool(pool)
cache = Cache("quickstart-async", maxsize=128, ttl=300, factory=factory)


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

The default policy suits most caches, but you can specify any built-in policy when creating the cache:

```python
from redis import Redis
from redis_func_cache import RedisFuncCache, fifo_policy, lfu_policy, rr_policy

pool = Redis.ConnectionPool.from_url("redis://")
factory = lambda: Redis.from_pool(pool)

# FIFO (First In, First Out)
fifo_cache = RedisFuncCache("my-fifo-cache", fifo_policy, factory=factory)

# LFU (Least Frequently Used)
lfu_cache = RedisFuncCache("my-lfu-cache", lfu_policy, factory=factory)

# Random Replacement
rr_cache = RedisFuncCache("my-rr-cache", rr_policy, factory=factory)
```

Available policies:

- **[`lru_t_policy`][]** (Default, recommended): Time-based LRU, offers the best balance of performance and accuracy for most use cases. It is the default when the `policy` argument is omitted.
- [`fifo_policy`][]: First in, first out
- [`gdsf_policy`][]: Greedy-Dual-Size — evicts the smallest benefit per byte (`frequency × cost / size`); supports the `cost` decorator kwarg (see [considerations](considerations.md))
- [`hyperbolic_policy`][]: Hyperbolic caching (LFU with aging) — frequency and insertion age in one score, so stale hot entries age out
- [`lfu_policy`][]: Least frequently used
- [`lru_policy`][]: Least recently used (more precise but slower than LRU-T)
- [`lru_tr_policy`][]: LRU-T with random admission — rejects ~half of the new insertions to blunt scan pollution (requires Redis ≥ 7.0; see [considerations](considerations.md))
- [`mru_policy`][]: Most recently used
- [`rr_policy`][]: Random remove

> ℹ️ **Info:**\
> Explore the source code in the directory `src/redis_func_cache/policies` for more details.

[redis]: https://redis.io/ "Redis is an in-memory data store used by millions of developers as a cache"
[`RedisFuncCache`]: redis_func_cache.cache.RedisFuncCache
[`fifo_policy`]: redis_func_cache.policies.fifo.fifo_policy "First In First Out policy"
[`gdsf_policy`]: redis_func_cache.policies.gdsf.gdsf_policy "Greedy-Dual-Size policy"
[`hyperbolic_policy`]: redis_func_cache.policies.hyperbolic.hyperbolic_policy "Hyperbolic (LFU with aging) policy"
[`lfu_policy`]: redis_func_cache.policies.lfu.lfu_policy "Least Frequently Used policy"
[`lru_policy`]: redis_func_cache.policies.lru.lru_policy "Least Recently Used policy"
[`lru_tr_policy`]: redis_func_cache.policies.lru.lru_tr_policy "LRU-T with random admission policy"
[`mru_policy`]: redis_func_cache.policies.mru.mru_policy "Most Recently Used policy"
[`rr_policy`]: redis_func_cache.policies.rr.rr_policy "Random Remove policy"
[`lru_t_policy`]: redis_func_cache.policies.lru.lru_t_policy "Time based Least Recently Used policy."
