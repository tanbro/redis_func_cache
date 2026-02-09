# redis_func_cache

Python decorator library for caching function results in Redis - a distributed alternative to `functools.lru_cache`.

## Quick Start

```bash
# Install with dev dependencies (uv is preferred)
uv sync --all-groups --dev
# Or with pip
pip install -e ".[all]" && pip install -e ".[test,docs,typed]" --group dev

# Install pre-commit hooks
pre-commit install

# Start Redis for testing
cd docker && docker compose up
```

## Commands

```bash
# Run tests
python -m unittest
pytest -xv --cov

# Code quality
pre-commit run -a
ruff check --fix
ruff format
mypy

# Build package
pip install build
python -m build
```

## Architecture

### Core Design Patterns

- **Strategy Pattern**: Policies implement `AbstractPolicy` with pluggable eviction algorithms (LRU, FIFO, LFU, etc.)
- **Mixin Pattern**: Policies compose behavior via `HashMixin` (serialization/hashing) + `ScriptMixin` (Lua scripts)
- **Weakref Pattern**: Policies hold weakref to cache to prevent circular references

### Directory Structure

```
src/redis_func_cache/
├── __init__.py          # Main exports: RedisFuncCache, all policy classes
├── cache.py             # Core RedisFuncCache class (decorator implementation)
├── constants.py         # Default values (prefix, default_ttl, etc.)
├── exceptions.py        # Custom exceptions
├── typing.py            # Type definitions
├── utils.py             # Utility functions (b64digest, bytecode extraction)
├── lua/                 # Redis Lua scripts (one pair per policy: *_get.lua, *_put.lua)
│   ├── lru_get.lua
│   ├── lru_put.lua
│   └── ...
├── policies/            # Cache eviction policy implementations
│   ├── abstract.py      # AbstractPolicy base class
│   ├── base.py          # BaseSinglePolicy, BaseMultiplePolicy, etc.
│   ├── lru.py           # LruPolicy, LruTPolicy (time-based LRU)
│   ├── fifo.py          # FifoPolicy, FifoTPolicy
│   ├── lfu.py           # LfuPolicy
│   ├── mru.py           # MruPolicy
│   └── rr.py            # RrPolicy (Random Replacement)
└── mixins/              # Mixin classes for policy composition
    ├── hash.py          # AbstractHashMixin, JsonSha1HexHashMixin, PickleMd5HashMixin, etc.
    └── scripts.py       # LruScriptsMixin, FifoScriptsMixin, etc.
```

### Policy Architecture

Policies come in **4 variants** based on key distribution and cluster support:

| Variant                 | Description                             | Key Pattern                           | Use Case                   |
| ----------------------- | --------------------------------------- | ------------------------------------- | -------------------------- |
| `SinglePolicy`          | All functions share same Redis key pair | `prefix:name:policy:0\|1`             | Simple use cases           |
| `MultiplePolicy`        | Each function gets its own key pair     | `prefix:name:policy:func#hash:0\|1`   | Isolate function caches    |
| `ClusterSinglePolicy`   | Hash tags for Redis Cluster             | `prefix{name:policy}:0\|1`            | Cluster with shared keys   |
| `ClusterMultiplePolicy` | Per-function keys with cluster support  | `prefix:name:policy:func{#hash}:0\|1` | Cluster with isolated keys |

**Naming convention**: `LruPolicy`, `LruMultiplePolicy`, `LruClusterPolicy`, `LruClusterMultiplePolicy`

## Redis Data Structures

Each cache uses **TWO Redis keys** (suffix `:0` and `:1`):

- **`:0` suffix** → Sorted Set (ZSET): stores hash values with eviction scores
  - LRU: timestamp as score
  - LFU: access frequency as score
  - FIFO: insertion order as score

- **`:1` suffix** → Hash Map (HASH): stores `hash_value → serialized_return_value`

**Lua scripts** ensure atomic operations on both structures simultaneously.

## Key Files

- `src/redis_func_cache/__init__.py` - Public API exports
- `src/redis_func_cache/cache.py` - Core decorator logic (exec, aexec, decorate methods)
- `src/redis_func_cache/policies/abstract.py` - AbstractPolicy base interface
- `pyproject.toml` - Dependencies, build config, optional extras (hiredis, msgpack, bson, etc.)
- `.ruff.toml` - Line length 120, code style rules

## Code Style

- Type hints required throughout (mypy enforced)
- Ruff for linting/formatting (line length 120)
- Pre-commit hooks: ruff, mypy, markdownlint, trailing-whitespace
- Docstrings follow standard conventions

## Testing Patterns

- **Framework**: pytest with pytest-asyncio for async tests
- **Redis setup**: `cd docker && docker compose up` (required for most tests)
- **Fixtures**: Session-scoped event loop, cache cleanup in `conftest.py`
- **Test files**: `test_*.py` in `tests/` directory
- **Environment**: `REDIS_URL` defaults to `redis://localhost:6379`

## Package Management

- **Primary**: `uv` (fast Python package manager) - `uv sync --all-groups --dev`
- **Fallback**: `pip` with `pyproject.toml` - `pip install -e ".[all]"`
- **Dependency groups**: `dev`, `test`, `docs`, `typed`, `ipy`
- **Optional extras**: `[hiredis]`, `[msgpack]`, `[bson]`, `[yaml]`, `[cbor]`, `[cloudpickle]`

## Gotchas

### API Changes (v0.7+)

- **Policy instantiation**: Policies must be instantiated: `LruTPolicy()` not `LruTPolicy`
- **Factory pattern**: Use `factory=` for concurrent scenarios, not direct `client=` instances
- **Client vs Factory**: `client` is for single-use, `factory` creates new client per call (thread-safe)

### Architecture Constraints

- **Bytecode hashing**: Default hash includes function bytecode → caches incompatible across Python versions
- **Non-serializable args**: Use `excludes` or `excludes_positional` to skip unserializable arguments
- **Async/sync separation**: Async cache requires async Redis client AND async functions
- **Lua script atomicity**: All operations atomic within single Redis node, but **cache stampede** possible on misses (multiple threads may all execute function)

### Redis Integration

- **Dual data structures**: ZSET (scoring) + HASH (storage) - must be maintained together
- **Cluster compatibility**: Use `*ClusterPolicy` variants with hash tags `{}` for same-slot guarantee
- **Serialization**: Default JSON (safe), pickle available but dangerous with untrusted data
- **TTL modes**: Structure-level TTL (sliding/fixed) vs per-item TTL (Redis 7.4+, experimental)
