# Changelog

## v0.3 (In Development)

- ✨ **New Features:**
  - Added setter methods for the `name`, `prefix`, `maxsize`, `ttl`, and `serializer` properties in the `RedisFuncCache` class.
  - Introduced support for `msgpack` and `cloudpickle`.
  - Added a "per-function" custom serializer feature to the `RedisFuncCache` class.

- 💔 **Broken changes:**
  - The `lru-t` policy class have been moved to `policies/lru` module
  - The `fifo-t` policy class have been moved to `policies/fifo` module

- 🛠️ **Improvements:**
  - Updated the default values of several arguments in the `RedisFuncCache` constructor.
  - Improved type casting in the `cache` module.

- 📦 **Packaging:**
  - Added `msgpack` and `cloudpickle` as optional dependencies.
  - Adjusted the `manifest.in` file.

- 🧪 **Tests:**
  - Added new tests for multiple and cluster key caching.
  - Fixed asynchronous bugs in existing tests.
  - Optimized Docker Compose-based tests.

- ⚙️ **CI:**
  - Added Redis cluster tests in GitHub Actions.
  - Fixed issues with `codecov` coverage upload.
  - PyPY testings removed from `tests/run.sh`

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
