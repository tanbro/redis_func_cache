# Configuration

## Cache Size and TTL

Control cache size and expiration:

```python
cache = RedisFuncCache(
    "my-cache",
    LruTPolicy(),
    redis_client=redis_client,
    maxsize=100,  # Maximum number of cached items
    ttl=300,  # Cache expires after 300 seconds of inactivity
)
```

- **`maxsize`**: Maximum number of items the cache can hold. When reached, items are evicted according to the policy.
- **`ttl`**: Time-to-live in seconds. The entire cache structure expires after this period of inactivity (sliding expiration).

For "multiple" policies, each decorated function has its own independent data structure, so `maxsize` and `ttl` apply to each function's cache individually.

### Runtime Size Adjustment

`maxsize` is settable at runtime, which is handy for adaptive sizing based on observed hit rates:

```python
cache.maxsize = cache.maxsize * 2
```

The change is **lazy**: growing takes effect immediately on subsequent writes, while shrinking takes effect on the **next write**, which then evicts all excess items in one batch. Size a shrink burst accordingly when a large cache is downsized.

### Sliding Expiration Semantics

When `ttl` is set, the structure TTL is refreshed on every **hit** and every **write** (if `update_ttl` is enabled). A **miss** never slides the expiration — instead, a miss cleans up the stale entry it probed (one-item lazy vacuum; see also `vacuum` in the *Cache Maintenance* section below).

### Per-Item TTL (Experimental)

You can also set TTL on individual cached items:

```python
@cache(ttl=300)  # Each result expires after 300 seconds
def my_func(x): ...
```

> ⚠️ **Warning:** This feature requires [Redis][] 7.4+ and uses [Redis Hashes Field expiration](https://redis.io/docs/latest/develop/data-types/hashes/#field-expiration). When a field expires, it's removed from the HASH but the corresponding entry in the ZSET is only lazily cleaned up. Use `vacuum` (see the *Cache Maintenance* section below) to reclaim those slots on demand.

## Serialization

The default serializer is [JSON][], which works with simple data types. For complex objects, you can specify alternative serializers:

```python
import pickle
from redis_func_cache import RedisFuncCache, LruTPolicy

# Method 1: Set at cache instance level
cache = RedisFuncCache(
    __name__,
    LruTPolicy(),
    factory=lambda: Redis.from_url("redis://"),
    serializer="pickle",  # or (pickle.dumps, pickle.loads)
)


# Method 2: Override at decorator level
@cache(serializer="pickle")
def my_func_with_complex_return(x):
    return {...}  # Complex object
```

Supported serializers: JSON, Pickle, Dill, MsgPack, YAML, BSON, CBOR, and cloudpickle.

> ⚠️ **Warning:** [`pickle`][] and `dill` can execute arbitrary code during deserialization. Use with extreme caution, especially with untrusted data.

## Handling Non-Serializable Arguments

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

## Multiple Key Pairs

By default, all decorated functions share the same Redis key pair. To give each function its own keys, use a "Multiple" policy:

```python
from redis_func_cache import RedisFuncCache, LruTMultiplePolicy

cache = RedisFuncCache("my-cache", LruTMultiplePolicy(), redis_client=redis_client)


@cache
def func1(x): ...


@cache
def func2(x): ...


# func1 and func2 have separate Redis key pairs
```

Available multiple-key policies: [`FifoMultiplePolicy`][], [`LfuMultiplePolicy`][], [`LruMultiplePolicy`][], [`LruTMultiplePolicy`][], [`MruMultiplePolicy`][], [`RrMultiplePolicy`][].

## Redis Cluster

For Redis Cluster deployments, use a Cluster-aware policy. These policies use hash tags `{...}` to ensure both keys are on the same cluster node:

```python
from redis_func_cache import RedisFuncCache, LruTClusterPolicy

cache = RedisFuncCache("my-cache", LruTClusterPolicy(), redis_client=redis_client)


@cache
def my_func(x): ...
```

Available cluster policies: [`FifoClusterPolicy`][], [`LfuClusterPolicy`][], [`LruClusterPolicy`][], [`LruTClusterPolicy`][], [`MruClusterPolicy`][], [`RrClusterPolicy`][].

For per-function keys in cluster mode, use `*ClusterMultiplePolicy` variants: [`LruTClusterMultiplePolicy`][], etc.

## Cache Maintenance

Per-item TTL expiry (see *Per-Item TTL* above) removes the HASH field but leaves the corresponding member in the index structure (ZSET or SET). Such "ghost" entries can be reclaimed on demand:

```python
removed = cache.vacuum(batch_size=500)  # Returns the number of ghosts removed
```

For async caches, use `await cache.avacuum()`. Each invocation scans incrementally (in `batch_size` chunks) and is atomic per step, so it is safe to run while the cache is serving traffic.

Note on size reporting: `cache.policy.get_size()` returns the index structure cardinality — the same number the eviction script enforces `maxsize` against. Ghost entries keep it elevated until reclaimed; the count of live values is the HASH length (`HLEN`) of the second key from `cache.policy.calc_keys(fn)`.

## Cache Mode Control

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
