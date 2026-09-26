# Migration Guide

## v0.x → v1.0

v1.0 replaces the mixin-based policy architecture with **composition**. The
everyday decorator API — pick a built-in policy, pass it to `RedisFuncCache`,
decorate with a bare `@cache` — is unchanged:

```python
cache = RedisFuncCache("my-cache", LruPolicy, factory=factory)

@cache
def my_func(x): ...
```

Built-in policies are now preset `Policy` **instances** (previously classes you
instantiated): pass `LruPolicy` itself, not `LruPolicy()`. RedisFuncCache
snapshot-copies the policy it is given, so sharing a preset across caches is
safe. Key names, hash values, Lua scripts and the ARGV layout are unchanged —
existing Redis data stays readable (golden tests pin this contract).

### Summary of Changes

- The `mixins/` package (`hash.py`, `scripts.py`) and `policies/abstract.py` /
  `policies/base.py` are removed.
- New components: `keying.py` (`SingleKeying`, `MultipleKeying`,
  `ClusterSingleKeying`, `ClusterMultipleKeying`), `hashing.py`
  (`Hasher`, `HashConfig`, presets such as `PickleMd5Hasher`) and
  `scripts.py` (`LruScripts`, `RrScripts`, ...).
- `Policy(keying, hasher, scripts)` composes the three dimensions and exposes
  the same facade the cache calls (`calc_key_pair`, `calc_hash`, `purge`,
  `get_size`, `vacuum`, ...).
- The hash factory `make_hash_mixin` is replaced by
  [`make_hasher`][redis_func_cache.hashing.make_hasher]; `make_scripts_mixin`
  is removed (a :class:`~redis_func_cache.scripts.Scripts` subclass is the way).
- `get_size`/`aget_size` report the index-structure cardinality (ZCARD, SCARD
  for RR) instead of HLEN, matching what `maxsize` enforcement uses.
- Policy methods that talk to Redis take the client as an explicit first
  parameter named `redis_client`: `purge`, `apurge`, `get_size`, `aget_size`,
  `vacuum`, `avacuum`, and `iterate_key_pairs` / `aiterate_key_pairs`. The script
  registration (`lua_scripts` / `vacuum_script`) likewise moved to the
  `scripts` component as methods taking `redis_client` — no more cached
  `Script` objects bound to a stale client. The cache obtains the client from
  your `redis_client=` / `factory=` and passes it down, so the cache-level API
  (`cache.purge()`, `cache.vacuum()`, ...) is unchanged.
- `RedisFuncCache.__init__`: the `client` parameter is removed — use
  `redis_client=` (passing a callable as `redis_client` was already
  deprecated in v0.7; use `factory=`). `cache.get_client()` is removed — use
  `cache.get_redis_client()`. Both old names were deprecated aliases that
  never shipped in a stable release, so they are gone without a transition.
- The policy no longer holds a back-reference to the cache; the cache copies
  the `prefix` / `name` namespace onto the policy at construction (accessible
  as `policy._prefix` / `policy._name`).
- The JSON serializer now emits `ensure_ascii=False` with compact separators.
  Existing cache entries are keyed differently and are invalidated once on
  upgrade, then repopulated transparently — no code change needed.

### Custom Policy Migration

**Old (v0.x):**

```python
from dataclasses import replace
from redis_func_cache.mixins.hash import JsonMd5HashMixin
from redis_func_cache.mixins.scripts import LruScriptsMixin
from redis_func_cache.policies.base import BaseSinglePolicy

class MyLruPolicy(LruScriptsMixin, JsonMd5HashMixin, BaseSinglePolicy):
    __key__ = "my-lru"
    __hash_config__ = replace(JsonMd5HashMixin.__hash_config__, use_bytecode=False)

cache = RedisFuncCache("my-cache", MyLruPolicy(), factory=factory)
```

**New (v1.0):**

```python
from dataclasses import replace
from redis_func_cache import RedisFuncCache
from redis_func_cache.hashing import JsonMd5Hasher
from redis_func_cache.keying import SingleKeying
from redis_func_cache.policies import Policy
from redis_func_cache.scripts import LruScripts

class MyHasher(JsonMd5Hasher):
    __hash_config__ = replace(JsonMd5Hasher.__hash_config__, use_bytecode=False)

my_policy = Policy(SingleKeying("my-lru"), MyHasher(), LruScripts())
cache = RedisFuncCache("my-cache", my_policy, factory=factory)
```

### Renamed API Quick Reference

| Old (v0.x)                                   | New (v1.0)                                        |
| -------------------------------------------- | ------------------------------------------------- |
| `LruPolicy()` (class instantiation)          | `LruPolicy` (preset instance)                     |
| `mixins.hash.*Mixin` classes                 | `hashing.*Hasher` classes                |
| `mixins.scripts.*ScriptsMixin` classes       | `scripts.*Scripts` classes               |
| `policies.abstract.AbstractPolicy`           | `policies.Policy`                                 |
| `policies.base.BaseSinglePolicy`             | `keying.SingleKeying` (composed)         |
| `policies.base.BaseMultiplePolicy`           | `keying.MultipleKeying` (composed)       |
| `policies.base.BaseClusterSinglePolicy`      | `keying.ClusterSingleKeying` (composed)  |
| `policies.base.BaseClusterMultiplePolicy`    | `keying.ClusterMultipleKeying` (composed)|
| `make_hash_mixin(name, config)`              | `make_hasher(name, config)` or a `Hasher` subclass |
| `policy.__key__` / `policy.__scripts__`      | `policy.keying.key` / `policy.scripts.get_script` |
| `policy.__hash_config__`                     | `policy.hasher.__hash_config__`                   |
| `RedisFuncCache.__serializers__`             | `serializers.SERIALIZERS` (module-level registry)  |
| `RedisFuncCache(client=...)`                 | `RedisFuncCache(redis_client=...)` (alias removed) |
| `cache.get_client()` / `cache.client`        | `cache.get_redis_client()` (aliases removed)       |
| `policy.cache`                               | `policy._prefix` / `policy._name`                  |
| `policy.vacuum_script` (property)            | `policy.scripts.vacuum_script(redis_client)`       |
| `policy.lua_scripts` (property)              | `policy.scripts.lua_scripts(redis_client)`         |

## v0.6 → v0.7

v0.7 introduced breaking changes to the `RedisFuncCache` constructor:

## Summary of Changes

- The Redis client parameters renamed to `client` and `factory`. `factory` is preferred for concurrent/production use.
- The `policy` parameter must now be an **instance** (e.g., `LruTPolicy`), not a class.
- Passing a callable as the `client` positional argument is deprecated. Use `factory=` instead.

## Migration Example

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
cache = RedisFuncCache("my-cache", LruTPolicy, factory=factory)
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
