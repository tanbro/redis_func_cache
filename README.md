# redis_func_cache

[![python-package](https://github.com/tanbro/redis_func_cache/actions/workflows/python-package.yml/badge.svg)](https://github.com/tanbro/redis_func_cache/actions/workflows/python-package.yml)
[![codecov](https://codecov.io/gh/tanbro/redis_func_cache/graph/badge.svg?token=BgeXJZdPbJ)](https://codecov.io/gh/tanbro/redis_func_cache)
[![readthedocs](https://readthedocs.org/projects/redis-func-cache/badge/)](https://redis-func-cache.readthedocs.io/)
[![pypi-version](https://img.shields.io/pypi/v/redis_func_cache.svg)](https://pypi.org/project/redis_func_cache/)

> _A Python library that provides decorators for caching function results in Redis, supporting multiple serialization formats and caching strategies, as well as asynchronous operations._

## Introduction

`redis_func_cache` is a Python library that provides decorators for caching function results in Redis, similar to the caching functionality offered by the standard library. Like the [`functools`](https://docs.python.org/library/functools.html) module, it includes useful decorators such as [`lru_cache`](https://docs.python.org/library/functools.html#functools.lru_cache), which are valuable for implementing memoization.

Unlike in-process caches such as the standard library's `functools.lru_cache` — which are private to a single Python process — this library uses [Redis][] as a **distributed cache backend**: a result computed once is shared by every process and machine behind your application, and survives restarts and deploys. Decorated functions keep their ordinary look and feel; the distributed part is handled by the library:

- **Shared across processes and hosts** — one cache for all workers, no per-process duplication.
- **Works with any [Redis][] deployment** — standalone, Sentinel-managed replication, or [Redis][] Cluster (dedicated policies pin each cache's keys to one hash slot). The library adds no infrastructure of its own.
- **Atomic operations** — every cache read/write is a single Lua script executed atomically by [Redis][], safe under high concurrency.
- **Pluggable eviction policies** — LRU, LFU, FIFO, GDSF, Hyperbolic, ...; each decorated function is an independent logical cache with its own algorithm and maxsize, chosen at decoration time.

## Example

Cache a function — async or sync — with one decorator:

```python
from redis.asyncio import ConnectionPool, Redis
from redis_func_cache import RedisFuncCache as Cache

pool = ConnectionPool.from_url("redis://")
cache = Cache(__name__, factory=lambda: Redis.from_pool(pool))

@cache
async def get_data():          # your slow function — any function
    await asyncio.sleep(10)
    return "expensive result"

await get_data()   # 10 s  — computed and stored in Redis
await get_data()   # 0.00x s — served from Redis, shared by every process
```

Every process and machine behind your application now shares this one cache. To run this yourself step by step — including starting a Redis server — see [Quick Start](docs/usage/quickstart.md).

## Features

- Built on [redis-py][], the official Python client for [Redis][] — which is also the **only** runtime dependency (plus `typing-extensions` on Python < 3.12); the optional serialization formats are extras, and each is used only if its package is installed and selected.
- Simple [decorator][] syntax supporting both **`async`** and common functions, **asynchronous** and synchronous I/O.
- Support [Redis][] **Cluster**.
- Eviction policies: LRU, LFU, FIFO, MRU, RR, GDSF (cost-aware), Hyperbolic, LRU with random admission — pluggable, composable from keying / hasher / scripts components.
- Serialization formats: JSON, Pickle, Dill, MsgPack, YAML, BSON, CBOR, cloudpickle ...
- Optional **handler** extension around the four serialization boundaries — async-aware, settable per cache or per function, for patterns like offloading large values to object storage while Redis stores only a small reference.
- Per-item TTL (Redis ≥ 7.4).
- Maintenance operations: `vacuum` to clean expired entries, `purge` to drop all cache structures — both without blocking Redis.

## How it works

The [`RedisFuncCache`][] executes a decorated function with specified arguments and caches its result. Here's a breakdown of the steps:

1. **Initialize Scripts**: Register the policy's two Lua scripts (cache hit and update) against the Redis client, cached per client.
1. **Locate the Call**: Compute the call identity — key pair and hash value — once; the same identity is shared by the handler context and the get/put script invocation.
1. **Attempt Cache Retrieval**: Attempt to retrieve a cached result. If a cache hit occurs, deserialize and return the cached result.
1. **Execute User Function**: If no cache hit occurs, execute the decorated function with the provided arguments and keyword arguments.
1. **Store the Result**: Serialize the result of the user function and store it in Redis.
1. **Return Result**: Return the result of the decorated function.

Under the hood, the library combines a pair of [Redis][] data structures to manage cache data:

- The first is a sorted set, which stores the hash values of the decorated function calls along with a score for each item.

  When the cache reaches its maximum size, the score is used to determine which item to evict.

- The second is a hash map, which stores the hash values of the function calls and their corresponding return values.

This can be visualized as follows:

![data_structure](images/data_structure.svg)

The main idea of the eviction policy is that the cache keys are stored in a set, and the cache values are stored in a hash map. Eviction is performed by removing the lowest-scoring item from the set, and then deleting the corresponding field and value from the hash map.

Here is an example showing how the _LRU_ cache's eviction policy works (maximum size is 3):

![eviction_example](images/eviction_example.svg)

## Install

```bash
pip install redis_func_cache[hiredis]
```

[hiredis](https://github.com/redis/hiredis) is a strongly recommended optional extra that can significantly improve performance; [Pygments](https://pygments.org/) is another — if installed, it shrinks the Lua scripts sent to the [Redis][] server. For other installation methods (from source, from GitHub) see [CONTRIBUTING.md](https://github.com/tanbro/redis_func_cache/blob/main/CONTRIBUTING.md#development-setup).

## Concurrency and atomicity

Every cache read/write is a **single Lua script executed atomically** by the [Redis][] server — safe under high concurrency with no extra locking. On [Redis][] Cluster, atomicity holds as well: the cluster policies pin each cache's two keys to one hash slot on the same node.

The cache issues these scripts through the [redis-py][] client you supply (directly or via a `factory`); it does not manage connections itself. Client thread safety, event-loop affinity and fork behavior are defined by redis-py — prefer the **factory and pool** pattern (lightweight clients sharing one pre-configured pool):

```python
redis_pool = redis.ConnectionPool(...)  # Use a pool, not a single client
factory = lambda: redis.from_pool(redis_pool)  # Use a factory, not a static client

cache = RedisFuncCache(__name__, lru_policy, factory=factory)
```

See [Concurrency and Atomicity](docs/usage/considerations.md#concurrency-and-atomicity) in the documentation for the full guidance (event loops, fork safety, function-level concurrency, contextual state isolation).

## Documentation

More documentation is available in the [`docs`](https://github.com/tanbro/redis_func_cache/tree/main/docs) directory (and rendered at [Read the Docs](https://redis-func-cache.readthedocs.io/)):

- [Quick Start](docs/usage/quickstart.md) — prerequisites, a first cached function, choosing an eviction policy
- [Eviction Policies](docs/usage/eviction-policies.md) — the built-in policies and presets, choosing and composing your own
- [Advanced Usage](docs/usage/advanced-usage.md) — custom serializers, custom key formats and hash algorithms
- [Handlers](docs/usage/handlers.md) — the handler extension around the serialization boundaries (e.g. offloading large values to object storage)
- [Configuration](docs/usage/configuration.md) — cache size & TTL, per-item TTL, serialization, `excludes`, multiple key pairs, cluster policies, cache mode control
- [Important Considerations](docs/usage/considerations.md) — concurrency & atomicity, cache stampede risk, known issues and limitations
- [Migration Guide](docs/usage/migration.md) — 0.x → 1.0 breaking changes and migration

## Cache Maintenance

Two explicit operations, both non-blocking for Redis:

- **`vacuum`** — with a per-item `ttl` (Redis ≥ 7.4), expired results leave "ghost" entries in the sorted-set index; `vacuum` scans it in batches and removes them (`avacuum()` is the async mirror).
- **`purge`** — deletes every Redis key the cache owns, enumerating per-function key pairs with `SCAN` and deleting in batches with `UNLINK` (`apurge()` is the async mirror).

Details and examples: [Cache Maintenance](docs/usage/configuration.md#cache-maintenance).

## Known Issues

See [docs/considerations.md](docs/usage/considerations.md#known-issues) for the full list of known issues and limitations.

## Test

Start a Redis server, then run the test suite (a Docker Compose file in the `docker` directory can start Redis and run the whole suite for you). Detailed instructions — environment variables, the cluster test groups, and the Docker-based runner — are in [CONTRIBUTING.md](https://github.com/tanbro/redis_func_cache/blob/main/CONTRIBUTING.md#running-tests).

## Develop

To set up a development environment, clone the repository and see [CONTRIBUTING.md](https://github.com/tanbro/redis_func_cache/blob/main/CONTRIBUTING.md#development-setup) for the full setup (virtual environment, dependencies, [pre-commit][] hooks — some of which invoke host tools such as [uv][], Node.js and `lua-language-server` — plus coding conventions and the architecture overview).

## Architecture

The library composes three orthogonal components into an eviction policy: **Keying** (key naming, with cluster hash-tag variants), **Hasher** (per-call sub-key computation) and **Scripts** (the Lua script declarations). Full module structure and class diagrams are documented in [CONTRIBUTING.md](https://github.com/tanbro/redis_func_cache/blob/main/CONTRIBUTING.md#architecture).

[redis]: https://redis.io/ "Redis is an in-memory data store used by millions of developers as a cache"
[redis-py]: https://redis.io/docs/develop/clients/redis-py/ "Connect your Python application to a Redis database"
[decorator]: https://docs.python.org/glossary.html#term-decorator "A function returning another function, usually applied as a function transformation using the @wrapper syntax"
[pre-commit]: https://pre-commit.com/ "A framework for managing and maintaining multi-language pre-commit hooks."
[uv]: https://docs.astral.sh/uv/ "An extremely fast Python package and project manager, written in Rust."
[`RedisFuncCache`]: redis_func_cache.cache.RedisFuncCache
