# Changelog

## v0.5

> 📅 developing (beta-1)

- ✨ **New Features:**
  - Added arguments excluding support for the `RedisFuncCache` class, which makes it possible to cache functions with arguments that cannot be serialized.

- 💔 **Breaking Changes:**
  - Rename `redis_func_cache.mixins.policies` to `redis_func_cache.mixins.scripts`.

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
