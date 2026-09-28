# Changelog

## v1.0 (unreleased)

- 💔 **Breaking Changes:**
  - **The policy layer is rebuilt from inheritance into composition.** The `AbstractPolicy` mixin hierarchy is replaced by a single `Policy(keying, hasher, scripts)` bundling three orthogonal components: a `Keying` (key naming: `SingleKeying` / `MultipleKeying` and their cluster variants), a `Hasher` (algorithm + serializer + optional bytecode in one `HashConfig`), and a `Scripts` (Lua script declaration, ARGV builders and per-client script registration). Custom policies are now composed — `Policy(SingleKeying(key), MyHasher(), LruScripts())` — instead of subclassing mixins; the built-in presets (`lru_policy`, `rr_policy`, ...) are argument-less, pre-composed `Policy` instances. `make_hasher(name, hash_config)` (see New Features) replaces the `make_hash_mixin` factory; `make_scripts_mixin` is removed. See `docs/usage/migration.md` for the full 0.x → 1.0 mapping.
  - **Policies are completely stateless.** A policy holds neither the cache nor the key namespace: the `AbstractPolicy.cache` back-reference (and its weakref) is gone, and `prefix` / `name` are explicit arguments on every policy method that needs them, supplied by `RedisFuncCache` at each call. Preset policy instances are therefore safe to share across caches and processes — there is never a reason to copy one.
  - **Policy methods that talk to Redis take the client explicitly.** Every Redis-touching policy method has `redis_client` as its first parameter (previously named `client` or obtained via an implicit `get_client()` reach-through): `purge_all_pairs(redis_client, prefix, name, batch_size=500)`, `apurge_all_pairs(...)`, `get_size(redis_client, prefix, name)`, `aget_size(...)`, `vacuum_all_pairs(redis_client, prefix, name, batch_size=500)`, `avacuum_all_pairs(...)`, `iterate_key_pairs(redis_client, prefix, name)` / `aiterate_key_pairs(...)`, and `get` / `put` / `aget` / `aput`. The old reach-through cached `Script` objects bound to whichever client was current on first access — under a `factory` every script call was funneled through that stale client, defeating the factory's thread isolation and, with multi-server factories, sending commands to the wrong server. `RedisFuncCache` obtains the client and passes it down, so the cache-level API (`cache.purge()`, `cache.vacuum()`, ...) is unchanged. Custom policies must adapt to the new signatures.
  - **Maintenance-method names state their granularity.** On the policy: `purge_all_pairs` / `apurge_all_pairs` (delete every key pair), `vacuum_all_pairs` / `avacuum_all_pairs`, and the pair-level primitives `purge_one_pair` / `apurge_one_pair` (delete one key pair outright) and `vacuum_one_pair` / `avacuum_one_pair` (sweep one pair), which take raw key names — typically from `iterate_key_pairs` — so their semantics are unambiguous under every keying variant. The same vocabulary applies to the `Keying` component — `purge_all_pairs` / `apurge_all_pairs` — whose methods are the semantic source that the policy forwards to. The cache-level facades keep the short names (`cache.purge()`, `cache.vacuum()`, ...) because the cache has exactly one granularity: the whole cache it names.
  - `RedisFuncCache.__serializers__` is removed — the serializer registry now lives at `redis_func_cache.serializers.SERIALIZERS`.
  - `RedisFuncCache.__init__`: the `client` parameter is removed — use `redis_client=`. (The deprecated alias never shipped in a stable release, so it is gone without a transition.)
  - `RedisFuncCache.get_client()` and the deprecated `client` property are removed — use `get_redis_client()`.

- ✨ **New Features:**
  - The `policy` argument of `RedisFuncCache` is now optional, defaulting to `lru_t_policy` (LRU-T: timestamp-scored pseudo LRU on a single key pair). Note that LRU-T's eviction ordering is second-granular — writes within the same second are evicted in arbitrary order among themselves; pass another preset or a custom policy for different semantics. Policies are stateless, so the shared default instance is safe.
  - `Policy.locate(prefix, name, fn, args, kwds)`: computes the `(key pair, hash value)` identity locating one call in the cache — the single place where `calc_key_pair` and `calc_hash` meet. Pure query, part of the policy's introspection surface; handy for inspecting which Redis keys and hash field a decorated call maps to. `Policy.get` / `put` / `aget` / `aput` accept an optional `located=` argument so a caller that already located the call (e.g. a handler-context builder) reuses the identity instead of re-hashing.
  - `make_hasher(name, hash_config)` in `redis_func_cache.hashing`: builds a `Hasher` subclass from a `HashConfig` (any `hashlib` algorithm, any serializer/decoder callables, optional `use_bytecode`) — for one-off combinations not covered by the 24 predefined hasher classes (e.g. msgpack + `sha3_256`). Returns a fresh class per call (no memoization: type checks should target `Hasher`); generated classes with standard parts hash identically to their hand-written equivalents.
  - `handler` option on `RedisFuncCache` (constructor) and on `decorate()` (per-function override): a single optional handler that wraps the four serialization boundaries — `before_serialize`, `after_serialize`, `before_deserialize`, `after_deserialize` — each with an `*_async` counterpart. Built for use cases the `serializer` pair cannot express, notably **offloading large values to object storage** (async I/O, per-invocation context, and per-boundary take-over). `HandlerProtocol` is a pure structural protocol — implementations need not inherit from it; conforming to its signatures is the contract, checked statically. A handler implements at least one method group — sync or `*_async` — for the path it serves, keeps the other group as `raise NotImplementedError` placeholders if unused, and defines every method of an implemented group (identity returns for boundaries it does not need). `before_*` methods return `(handled, value)` — when `handled` is true the library skips everything remaining on that side, including the corresponding `after_*` method; `after_*` methods return the replacement value directly. Every method receives an immutable `HandlerContext` (`keys`, `hash_value`, `func`, `args`, `kwds`) whose `args`/`kwds` are the same excludes-filtered arguments used for cache-key computation. The asynchronous path calls **only** the `*_async` methods (no async-to-sync fallback, so blocking I/O can never be introduced onto the event loop implicitly). Handler exceptions propagate with no library retry, degradation, or counting. `HandlerProtocol` and `HandlerContext` are exported from the package root. Design note: `docs/design/handler.md`.
  - `ignore_redis_errors` option on `RedisFuncCache` (constructor and per-call override on `exec`/`aexec`/`decorate`): when enabled, `RedisError`s raised by cache reads and writes are swallowed instead of propagating to the caller, so a failing Redis never takes the application down. Errors are counted in the cache statistics (`Stats.err`).
  - `vacuum()` / `avacuum()` maintenance operation to reclaim the ZSET slots of expired per-field TTL entries ("ghost" entries): scans the sorted set in batches with an atomic, cursor-passing Lua script and removes members whose hash field has expired. Returns the number of entries removed. See the design note `docs/design/field-ttl-vacuum.md`.
  - Cache-level `purge()` / `apurge()` delegations, so callers no longer need to reach into `cache.policy` to drop all cache structures. Both accept a `batch_size` argument (default 500).
  - `get_size()` / `aget_size()` on "multiple" policies: previously raised `NotImplementedError`, now return the total number of cached items across all decorated functions' key pairs.

- 🛠 **Improvements:**
  - Multiple-policy `purge_all_pairs` / `apurge_all_pairs` no longer use the blocking `KEYS` command followed by one giant `DEL`. Keys are now enumerated with `SCAN` and deleted in batches with `UNLINK` (default 500 keys per command), so purging a large cache never stalls the Redis server. Behavior and return value are unchanged. See the design note `docs/design/purge.md`.
  - Hot-path reductions: the per-callable fingerprint hash (fullname + bytecode) is now computed once per function object and cached in a new `fingerprint` module, shared by the hasher classes and the multiple policies (previously re-hashed on every call, twice under multiple policies); per-call logger lookups and empty-options JSON encoding are eliminated; the vacuum Lua script text is read from package resources once instead of on every `vacuum`/`avacuum` call. Hash values and Redis key names are unchanged.
  - Note on serializer output: the JSON serializer used for cache-key hashing and for storing return values now emits `ensure_ascii=False` and compact separators (`(",", ":")`). Non-ASCII arguments and values serialize smaller and faster, but the byte output changes — existing cache entries are keyed differently and are invalidated once on upgrade, then repopulated transparently.

- 📚 **Documentation:**
  - New design notes: "Handler System for `redis_func_cache`" (`docs/design/handler.md`), "Vacuuming Expired Per-Field Cache Entries" (`docs/design/field-ttl-vacuum.md`), "Purging Cache Structures Without Blocking Redis" (`docs/design/purge.md`).
  - README: new *Handler* section under Advanced Usage, including the handler-vs-serializer decision guide; the Custom Policy section now covers policy composition and `make_hasher` for combinations outside the predefined hasher classes.
  - Restructured the documentation into a usage guide: the monolithic README was split into `docs/usage/quickstart.md`, `configuration.md`, `considerations.md`, `advanced-usage.md`, and `migration.md`, with the README keeping only an overview that highlights distributed caching; all pages are wired into the Sphinx toctree.

## v0.8.0

> 📅 2026-09-17

- 💔 **Breaking Changes:**
  - Require Python 3.10 or later; Python 3.9 is no longer supported.
  - Require redis-py `>=5.2,<9`, replacing the previous `>=3.5.0` constraint.
  - Rename the callable parameter of the public policy extension methods `calc_key_pair`, `calc_hash`, and `calc_ext_args` from `f` to `fn`. Custom policies and direct keyword calls must migrate from `f=` to `fn=`.
  - Reject callables without a stable cross-process identity when calculating cache keys. Bound instance methods, `functools.partial` objects, callable instances, and built-in functions now raise `TypeError`; plain functions, static methods, and bound class methods remain supported.

- 🐛 **Bug Fixes:**
  - Preserve descriptor semantics when the cache decorator wraps synchronous or asynchronous static methods, allowing calls through both the class and an instance.

- ✨ **Improvements:**
  - Use explicit MessagePack settings (`use_bin_type=True` and `raw=False`) for stable `str` and `bytes` handling.
  - Accept `memoryview` values returned by redis-py when deserializing JSON and YAML data.
  - Provide actionable errors when a callable cannot be used to generate a stable cache identity.

- 📦 **Packaging:**
  - Migrate the build backend from setuptools/setuptools-scm to Hatchling/hatch-vcs.
  - Normalize optional dependency definitions while preserving the existing extra names.

- 📚 **Documentation:**
  - Clarify how `self` and `cls` participate in cache-key serialization, including `excludes_positional=[0]` and the supported classmethod decorator order.
  - Correct the explanation for unsupported built-in functions: the limitation is stable callable identity, not bytecode availability.

- 🛠 **Maintenance:**
  - Modernize type annotations to PEP 604 syntax and simplify static type-checking dependencies.
  - Update GitHub Actions to Node 24-compatible releases.

## v0.7.0

> 📅 2026-03-30

- 💔 **Breaking Changes:**
  - Constructor parameter rename: the Redis client parameters have been renamed to `client` and `factory` (keyword-only). `factory` is preferred for concurrent/production usage.
  - Policy must be an instance: the `policy` argument to `RedisFuncCache` now requires a pre-instantiated `AbstractPolicy` instance (e.g. `lru_t_policy()`), previously callers might have passed the policy class.
  - Passing a callable as the `client` positional argument is deprecated. Use `factory=` instead. The library will emit a `DeprecationWarning` when detecting the old pattern.

  Migration example:

  ```python
  # OLD
  cache = RedisFuncCache("my-cache", lru_t_policy, client=redis_client)

  # NEW (v0.7+)
  cache = RedisFuncCache("my-cache", lru_t_policy(), factory=lambda: redis.from_pool(redis.ConnectionPool(...)))
  ```

- 🛠 **Notes:**
  - The change to require policy instances was made to ensure policy objects can be bound to the cache (policies hold cache-specific state). Reuse of the same policy instance across multiple caches is discouraged; create a new policy object per cache if independent state is required.
  - Please update any code that relied on passing policy classes or that passed a callable as the `client` positional argument.

## v0.6.0

- 💔 **Breaking Changes:**
  - Drop support for Python 3.8
  - Upgrade build backend to `setuptools>=80`
- 🛠 **Improvements:**
  - Optimized cache eviction logic in Lua scripts to improve performance and correctness
  - Fixed issues with evicted keys handling in LRU cache implementation
  - Improved consistency in cache TTL handling across all cache policies
  - Simplified and unified code structure in all put scripts for better maintainability
  - Enhanced efficiency by replacing loops with batch operations in FIFO_T policy
- 🐛 **Bug Fixes:**
  - Fixed LRU cache score update logic that could cause incorrect eviction order
  - Corrected cache access frequency update logic in LFU policy
  - Fixed timestamp update logic in LRU-T policy
  - Fixed wrong usages of table unpack in Lua scripts
- 🧹 **Chore:**
  - Added Python 3.14 in CI and tests scripts

## v0.5

> 📅 2025-08-26

- ✨ **New Features:**
  - Added arguments excluding support for the `RedisFuncCache` class, which makes it possible to cache functions with arguments that cannot be serialized.
  - Added support for controlling cache TTL update behavior with `update_ttl` parameter.
  - Enhanced cache mode control with mode context managers:
    - `RedisFuncCache.mode_context()` for applying mode contextually
    - `RedisFuncCache.disable_rw()` as an alias for completely disabling cache read and write operations
    - `RedisFuncCache.read_only()` for read-only cache mode
    - `RedisFuncCache.write_only()` for write-only cache mode
  - Added new `RedisFuncCache.Stats` class for cache statistics, and `RedisFuncCache.stats_context()` for retrieving cache statistics in a context manager.
  - Added support for per-invocation's cache TTL(experimental).
  - Added `use_bytecode` attribute to `HashConfig` class.

- 💔 **Breaking Changes:**
  - Rename `redis_func_cache.mixins.policies` to `redis_func_cache.mixins.scripts`.
  - Remove `asynchronous` property and related checks, you must ensure to decorate an async function with a cache instance has asynchronous redis client and a common function with a cache instance has synchronous redis client.

- 👎 Deprecated:
  - The property `RedisFuncCache.cache` is deprecated, use `RedisFuncCache.get_cache()` instead

- 🛠 **Improvements:**
  - Optimized Lua scripts for better performance
  - Improved documentation and examples for cache mode control
  - Enhanced test coverage for new cache mode context managers

## v0.4

> 📅 2025-06-24

- ✨ **New Features:**
  - Added `bson` and `yaml` serializer/deserializer support for the `RedisFuncCache` class.
  - Added comprehensive unit tests for exception handling, unserializable objects, various argument types, cache purge, custom serializers, and high concurrency scenarios (multi-thread/thread pool/concurrent exception handling).

- 💔 **Breaking Changes:**
  - The `serializer` optional parameter in the `RedisFuncCache`'s `decorate` and `__call__` methods has been replaced. It now accepts a tuple of `(serializer, deserializer)` or simply the name of the serializer function.

- 🛠 **Improvements:**
  - Updated and optimized several Lua scripts to improve performance, reliability, and compatibility with Redis.
  - Refactored test code for better readability and maintainability.
  - Improved code style and type annotations across the codebase.
  - Improved Redis Lua script cleaning logic: now handles the absence of `pygments` or Lua lexer more gracefully, and marks these branches as uncovered for coverage tools.

- 📦 **Packaging:**
  - Added `bson`, `yaml` as optional dependencies, and `all` for all serializers.
  - Added `types-all`, `types-PyYAML`, and `types-Pygments` as optional dependencies for typing hints.
  - Build and dependency management migrated to [uv](https://docs.astral.sh/uv/).

- 📝 **Misc**
  - Minor adjustments to documentation and configuration files.

## v0.3

> 📅 2025-01-08

- ✨ **New Features:**
  - Added setter methods for the `name`, `prefix`, `maxsize`, `ttl`, and `serializer` properties in the `RedisFuncCache` class.
  - Introduced support for `msgpack` and `cloudpickle`.
  - Added "per-function" custom serializer/deserializer parameter to `RedisFuncCache`'s decorate method.

- 💔 **Breaking Changes:**
  - Moved the `lru-t` policy class to the `policies/lru` module.
  - Moved the `fifo-t` policy class to the `policies/fifo` module.
  - Renamed `size` to `get_size` and `asize` to `aget_size` in `AbstractPolicy` and its subclasses.

- 💹 **Improvements:**
  - The default hash function now calculates the hash value based on the callable's byte code instead of source code.
  - Updated the default values of several arguments in the `RedisFuncCache` constructor.
  - Improved type casting in the `cache` module.

- 📦 **Packaging:**
  - Added `msgpack` and `cloudpickle` as optional dependencies.
  - Adjusted the `manifest.in` file.

- 🧪 **Tests:**
  - Added more test cases.
  - Fixed asynchronous bugs in existing tests.
  - Optimized Docker Compose-based tests.

- ⚙️ **CI:**
  - Added Redis cluster tests in GitHub Actions.
  - Fixed issues with `codecov` coverage upload.
  - Removed PyPy testing from `tests/run.sh`.

## v0.2.2

> 📅 2024-12-23

- ✨ **New Features:**
  - New `fifo-t` (Timestamp based pseudo FIFO replacement policy)

- 🐛 **Bug Fixes:**
  - Wrong type checking for `redis.cluster.RedisCluster` and `redis.asyncio.cluster.RedisCluster`

- 🛠 **Improvements:**
  - Remove some un-used utilities

- 📦 **Packaging:**
  - Add `hiredis` extras requirements
  - Adjust `manifest.in` file

- 📚 **Documentation:**
  - Modify documentation for docker-composed unit testing

- 🧪 **Tests:**
  - New add cluster based tests
  - Improved docker-composed based tests

## v0.2.1

> 📅 2024-12-19

- ✨ **New Features:**
  - Added support for asynchronous operations.

- 🐛 **Bug Fixes:**
  - Resolved several known issues.
  - Eliminated duplicate parts in the function full name used as a key.

- 🛠 **Improvements:**
  - Enhanced type hints for better code clarity.
  - Provided more detailed documentation to improve user understanding.

## v0.1

> 📅 2024-12-17

The First release, it's an early version, do not use it in production.
