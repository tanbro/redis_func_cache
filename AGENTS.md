# AI AGENT Programming Instructions for redis_func_cache Project

## 🎯 AI Assistant Quick Start

### Project Overview
A Python Redis-based function caching library with decorator-based API, supporting multiple eviction policies and async/sync operations. Designed for high-performance caching with atomic operations.

### Essential Architecture Concepts
- **Strategy Pattern**: Pluggable eviction policies (LRU, LFU, FIFO, MRU, RR)
- **Dual Redis Structure**: ZSET (scoring) + HASH (storage) with atomic Lua operations
- **Composition**: `Policy(keying, hasher, scripts)` — three orthogonal components

### Critical API Rules (v0.9+)
```python
# ❌ WRONG: the decorator has no `policy=` parameter — unknown kwargs are
#    forwarded to the Lua script (they either crash or are silently ignored)
@cache(policy=LruTPolicy)

# ❌ WRONG: `name` and a policy *instance* are required constructor arguments;
#    policies themselves take no arguments (no maxsize/ttl/serializer here)
cache = RedisFuncCache("my-cache", LruTPolicy)
cache = RedisFuncCache(LruTPolicy)

# ✅ CORRECT: choose policy/maxsize/ttl/serializer at construction,
#    then decorate with a bare @cache
cache = RedisFuncCache("my-cache", LruTPolicy, factory=lambda: redis.Redis())

@cache
def my_func(x): ...

# ❌ NOT thread-safe (a single shared client instance)
cache = RedisFuncCache("my-cache", LruTPolicy, redis_client=redis_client)

# ✅ Thread-safe for concurrent use
cache = RedisFuncCache("my-cache", LruTPolicy, factory=lambda: redis.Redis())
```

## 🔍 Key Information Index

### Quick File References
- **Core Implementation**: `src/redis_func_cache/cache.py` - Main class (`exec`, `aexec`, `decorate` methods)
- **Policies**: `src/redis_func_cache/policies/` - All eviction policy implementations
- **Redis Structure**: Keys with `:0` suffix = ZSET, `:1` suffix = HASH
- **Lua Scripts**: `src/redis_func_cache/lua/` - Atomic operations on both structures
- **Hashers**: `src/redis_func_cache/policies/hashing.py` - JSON/pickle + md5/sha1/sha256/sha512 presets
- **Errors**: `src/redis_func_cache/exceptions.py` - Custom exceptions

### Common Issues to Flag
1. **Policy Placement**: Policies are argument-less instances passed to the constructor (`RedisFuncCache("my-cache", LruTPolicy)`); `maxsize`/`ttl`/`serializer` are constructor options, and the decorator has no `policy=` parameter
2. **Bytecode Sensitivity**: Default hash includes function bytecode → cross-version issues
3. **Client Mismatch**: Async cache requires `aioredis`, sync cache requires `redis.Redis`
4. **No Reference Cycles**: Since v0.9 the policy holds no reference to the cache — `prefix`/`name` are copied onto it at construction (the old weakref back-reference was removed)

### Directory Structure
```
Core Components:
├── src/redis_func_cache/cache.py          # RedisFuncCache class
├── src/redis_func_cache/__init__.py       # Public API exports
├── src/redis_func_cache/policies/         # Policy implementations
├── src/redis_func_cache/policies/         # keying.py / hashing.py / scripts.py / policy.py
└── src/redis_func_cache/lua/*.lua         # Atomic Lua scripts

Configuration:
├── pyproject.toml                        # Dependencies, build config
├── .ruff.toml                           # Linting rules
└── .pre-commit-config.yaml               # Quality hooks
```

## 🏗️ Technical Architecture

### Policy System (4 Variants)
| Policy Type | Key Pattern | Use Case | Cluster Support |
|-------------|-------------|----------|----------------|
| `SinglePolicy` | `prefix:name:policy:0\|1` | Shared cache | ❌ |
| `MultiplePolicy` | `prefix:name:policy:func#hash:0\|1` | Isolated functions | ❌ |
| `ClusterSinglePolicy` | `prefix{name:policy}:0\|1` | Shared cluster keys | ✅ |
| `ClusterMultiplePolicy` | `prefix:name:policy:func{#hash}:0\|1` | Isolated cluster keys | ✅ |

**Naming Convention**: `LruPolicy`, `LruMultiplePolicy`, `LruClusterPolicy`, `LruClusterMultiplePolicy`

### Redis Data Structure
Every cache uses **TWO Redis keys**:
- **`:0` suffix** → ZSET: eviction scores (timestamp/frequency/order)
- **`:1` suffix** → HASH: `hash_value → serialized_result`

**Atomic Operations**: Lua scripts ensure both structures are updated simultaneously.

### Policy Composition Architecture
- **Keying** (`policies/keying.py`): key naming (Single/Multiple x Cluster), purge and index enumeration; stateless, namespace passed explicitly
- **Hasher** (`policies/hashing.py`): computes the sub-key from function + args via `HashConfig`
- **Scripts** (`policies/scripts.py`): owns the get/put Lua files, the index structure (ZCARD vs SCARD for RR), and the ext_args ARGV contract (MRU flag on ARGV[7])
- **Policy** (`policies/policy.py`): composes the three and exposes the facade the cache calls. Built-in policies are preset `Policy` instances; `RedisFuncCache` snapshot-copies the policy it is given

### API Usage Patterns

#### Correct API Usage (v0.9+)
```python
# ✅ Policy instance at construction (policies take no arguments)
import redis

cache = RedisFuncCache("my-cache", LruPolicy, factory=lambda: redis.Redis())


@cache
def my_func(x): ...


# ✅ Async cache setup
import aioredis

async_cache = RedisFuncCache("my-cache", LruPolicy, factory=lambda: aioredis.from_url("redis://localhost"))
```

#### Important Rules
- **Async vs Sync**: Async cache requires `aioredis`, sync requires `redis.Redis`
- **Type Safety**: Client type mismatches are checked at runtime
- **Cannot Mix**: Don't use sync functions with async cache (and vice versa)

## 🚨 Common Anti-patterns

### Critical Architecture Issues
- **Reference Cycles**: None by design — since v0.9 the policy never references the cache (namespace copied at construction; the weakref back-reference was removed)
- **Bytecode Sensitivity**: Default hash includes bytecode → cross-version incompatibility
- **Cache Stampede**: Multiple threads may execute same function on cache miss
- **Serialization Failures**: Non-serializable args need `excludes` parameter

### Redis Integration Issues
- **Cluster Compatibility**: Regular policies fail in cluster - use `*ClusterPolicy`
- **Dual Structure**: ZSET + HASH must be maintained together
- **TTL Modes**: Structure-level (default) vs per-item (Redis 7.4+)

### Usage Pattern Issues

#### Bytecode Sensitivity Problem
Bytecode enters the hash through the policy's hasher `__hash_config__`; there
is no `exclude_bytecode=` option on the decorator. To disable it, define a custom
policy (see `docs/usage/considerations.md`):

```python
# ❌ Cache version-specific: built-in policies hash the function bytecode
cache = RedisFuncCache("my-cache", LruPolicy, factory=factory)


@cache
def expensive_func(x): ...


# ✅ Cross-version compatible: a JSON hasher with use_bytecode=False
from dataclasses import replace

from redis_func_cache import RedisFuncCache
from redis_func_cache.policies.hashing import JsonMd5Hasher
from redis_func_cache.policies.keying import SingleKeying
from redis_func_cache.policies.policy import Policy
from redis_func_cache.policies.scripts import LruScripts


class MyHasher(JsonMd5Hasher):
    __hash_config__ = replace(JsonMd5Hasher.__hash_config__, use_bytecode=False)


my_policy = Policy(SingleKeying("my-lru"), MyHasher(), LruScripts())
cache = RedisFuncCache("my-cache", my_policy, factory=factory)
```

#### Serialization Issues
```python
# ❌ Non-serializable arguments
class Unserializable:
    def __init__(self):
        self.file_handle = open("file.txt")


# ✅ Exclude problematic fields (`excludes` is a decorator option)
@cache(excludes=["obj.file_handle"])
def process_data(obj: Unserializable): ...
```

## 📦 Dependencies & Environment

### Package Management
**Primary Manager**: `uv`
```bash
# Install with all dependencies
uv sync --all-extras --dev

# Runtime dependencies only
uv sync --all-extras

# Update dependencies
uv sync --all-extras --dev --upgrade
```

### Optional Dependencies
```bash
# Performance extras
uv sync --extra hiredis      # Faster Redis implementation
uv sync --extra msgpack      # Fast binary serialization
uv sync --extra dill         # Extended pickle support

# Data format extras
uv sync --extra bson         # MongoDB BSON
uv sync --extra yaml         # YAML support
uv sync --extra cbor         # Concise Binary Object
uv sync --extra cloudpickle  # Enhanced pickle
```

## 🔧 Development Workflow

### Code Quality Standards
- **Type hints**: Required throughout (mypy enforced)
- **Ruff**: Linting with line length 120
- **Pre-commit hooks**: ruff, mypy, markdownlint
- **Docstrings**: Required for all public APIs

### Essential Commands
```bash
# Testing
uv run pytest -xv --cov                    # Run all tests with coverage
uv run pytest tests/test_lru.py -v         # Run specific test

# Code Quality
uv run pre-commit run -a                   # Run all quality checks
uv run ruff check --fix                    # Lint and auto-fix
uv run mypy                                 # Type checking

# Build & Release
uv build                                   # Build package
```

### Testing Environment
```bash
# Start Redis for testing
cd docker && docker compose up

# Default Redis URL for tests
REDIS_URL=redis://localhost:6379
```

**Test Framework**: pytest + pytest-asyncio
**Test Files**: `test_*.py` in `tests/` directory
**Coverage**: `--cov=src --cov-report=html`

### CI/CD Information
**Triggers**: Push to `main`, PR to `main`, config changes
**Jobs**: Cross-platform testing (Linux 3.10-3.14, macOS), code quality, PyPI release
**Note**: Windows CI disabled for focused testing

## 📊 Serialization Options

### Default: JSON (Recommended for safety)
```python
from redis_func_cache import LruPolicy, RedisFuncCache

# JSON is the default `serializer` of RedisFuncCache(...)
cache = RedisFuncCache(__name__, LruPolicy, factory=factory)


# Standard JSON serialization
@cache
def compute_data(x):
    return {"result": x * 2}
```

### Performance Optimized Serializers
`serializer` is a `RedisFuncCache(...)` option and can be overridden per function
on the decorator (`json`, `pickle`, `dill`, `msgpack`, `yaml`, `bson`, `cbor`,
`cloudpickle`; names other than `json`/`pickle` require the matching extra):

```python
# Fastest for binary data (recommended for embeddings)
@cache(serializer="msgpack")
def compute_data(x):
    return x * 2


# Extended pickle support
@cache(serializer="dill")
def compute_data(x):
    return x * 2


# MongoDB compatibility
@cache(serializer="bson")
def compute_data(x):
    return x * 2
```

## 💡 Caching Strategies & Patterns

### Performance-Critical Operations
Cache expensive computations to improve response times and reduce resource usage.

#### API Call Caching
```python
import redis
from redis_func_cache import LruPolicy, RedisFuncCache

# maxsize/ttl belong to the RedisFuncCache(...) constructor, not the policy or decorator
cache = RedisFuncCache(__name__, LruPolicy, maxsize=1000, ttl=3600, factory=factory)


# Cache expensive external API calls
@cache
def fetch_api_data(endpoint: str, params: dict):
    """Cache API responses to reduce rate limits and costs."""
    response = requests.get(endpoint, params=params)
    return response.json()


# Same cache; for cross-version compatibility see the Bytecode Sensitivity
# Problem section above (custom policy with use_bytecode=False)
@cache
def api_call_with_retry(params: dict):
    """API calls with retry logic."""
    return fetch_api_data("/api/endpoint", params)
```

#### Data Processing Caching
```python
# Cache complex computations (maxsize set at construction)
process_cache = RedisFuncCache(__name__, LruPolicy, maxsize=500, factory=factory)


@process_cache
def process_large_dataset(data: list, config: dict):
    """Cache expensive data processing operations."""
    processed = []
    for item in data:
        result = apply_transformations(item, config)
        processed.append(result)
    return processed


# Cache text preprocessing (for cross-version compatibility, build a separate
# cache on a custom policy with use_bytecode=False — see Bytecode Sensitivity)
@cache
def preprocess_text(text: str, cleaning_rules: dict):
    """Cache text cleaning operations."""
    cleaned = text.lower()
    if "remove_punctuation" in cleaning_rules:
        cleaned = re.sub(r"[^\w\s]", "", cleaned)
    return cleaned
```

### Advanced Caching Patterns

#### Multi-Parameter Caching
```python
# Cache with multiple parameters for granular control — a "multiple" policy
# gives each decorated function its own key pair
multi_cache = RedisFuncCache(__name__, LruMultiplePolicy, maxsize=1000, factory=factory)


@multi_cache
def complex_calculation(input_data: str, algorithm: str, version: int):
    """Cache different algorithm variations separately."""
    return apply_algorithm(input_data, algorithm, version)
```

#### Time-Based Invalidation
```python
# Cache with automatic expiration for time-sensitive data
# (structure-level ttl is a RedisFuncCache(...) option, sliding expiration)
market_cache = RedisFuncCache(__name__, LruPolicy, maxsize=1000, ttl=300, factory=factory)  # ttl: 5 minutes


@market_cache
def get_market_data(symbol: str):
    """Cache market data with automatic refresh."""
    return market_api.get_current_data(symbol)
```

#### Memory-Constrained Environments
```python
# Limit the number of cached items (there is no byte-size `max_size_mb` option)
file_cache = RedisFuncCache(__name__, LruPolicy, maxsize=200, factory=factory)


@file_cache(serializer="msgpack")
def process_large_file(file_path: str, processing_options: dict):
    """Process large files with memory limits."""
    return process_file(file_path, processing_options)
```

### Cache Monitoring & Optimization

#### Performance Tracking
```python
import time

from redis_func_cache import LruPolicy, RedisFuncCache

# Create the cache (maxsize is a constructor option)
cache = RedisFuncCache(__name__, LruPolicy, maxsize=1000, factory=lambda: redis.Redis())


def monitor_cache_performance(run_traffic):
    """Track cache hit rates over each monitoring interval."""
    while True:
        with cache.stats_context() as stats:  # collect statistics for this interval
            run_traffic()

        total = stats.hit + stats.miss
        hit_rate = stats.hit / total if total else 0.0

        print(f"Cache Hit Rate: {hit_rate:.2%}")
        print(f"Hits: {stats.hit}, Misses: {stats.miss}, Errors: {stats.err}")

        # Adjust cache size based on performance (maxsize is settable at runtime)
        if total and hit_rate < 0.5:  # Low hit rate
            cache.maxsize = min(cache.maxsize * 2, 5000)

        time.sleep(60)
```

### Caching Best Practices

1. **Selective Caching**: Cache only expensive operations (compute time > cache lookup time)
2. **Appropriate TTLs**: Use TTL for time-sensitive data, None for static data
3. **Size Management**: Set reasonable maxsize values based on available memory
4. **Serialization Choice**: Use msgpack for binary data, JSON for human-readable data
5. **Cross-Version Compatibility**: For shared environments, compose a policy whose hasher sets `use_bytecode=False` (see the Bytecode Sensitivity Problem section)
6. **Error Handling**: Plan for cache failures gracefully

### Common Anti-patterns

```python
# maxsize/ttl are configured once, at construction
cache = RedisFuncCache(__name__, LruPolicy, maxsize=100, factory=factory)
fx_cache = RedisFuncCache(__name__, LruPolicy, ttl=300, factory=factory)  # 5 minutes


# ❌ Cache trivial operations (overhead > benefit)
@cache
def simple_addition(x, y):
    return x + y


# ✅ Cache expensive operations
@cache
def complex_ml_inference(data):
    return model.predict(data)


# ❌ No expiration for time-sensitive data
@cache
def get_exchange_rate(from_currency, to_currency):
    return forex_api.get_rate(from_currency, to_currency)


# ✅ Appropriate expiration
@fx_cache
def get_exchange_rate(from_currency, to_currency):
    return forex_api.get_rate(from_currency, to_currency)
```

## 🚀 Getting Started

### Development Setup
```bash
# 1. Install dependencies
uv sync --all-extras --dev

# 2. Install pre-commit hooks (MANDATORY)
pre-commit install

# 3. Start Redis
cd docker && docker compose up

# 4. Run tests
uv run pytest

# 5. Make changes with pre-commit hooks
# 6. Create PR - CI runs automatically
# 7. On merge to main + tag → PyPI publish
```

### Performance-Focused Setup
```bash
# 1. Install with performance extras
uv sync --all-extras --dev --extra msgpack --extra dill

# 2. Set up Redis
cd docker && docker compose up

# 3. Run performance tests
uv run pytest tests/test_performance.py -v

# 4. Monitor cache behavior
uv run python scripts/monitor_cache.py
```

### Common Use Cases

#### API Response Caching
```python
weather_cache = RedisFuncCache(__name__, LruPolicy, maxsize=2000, ttl=3600, factory=factory)


# Cache external API responses
@weather_cache
def fetch_weather_data(city: str, units: str = "metric"):
    """Cache weather API responses to reduce rate limits."""
    return weather_api.get_current_weather(city, units)
```

#### Data Processing Pipeline
```python
finance_cache = RedisFuncCache(__name__, LruMultiplePolicy, maxsize=1000, factory=factory)


# Cache complex data transformations
@finance_cache(serializer="msgpack")
def process_financial_data(raw_data: dict, analysis_config: dict):
    """Cache financial analysis results."""
    return analyze_data(raw_data, analysis_config)
```

#### Batch Processing
```python
batch_cache = RedisFuncCache(__name__, LruPolicy, maxsize=500, ttl=7200, factory=factory)


# Cache batch processing results
@batch_cache
def process_batch(file_ids: list, processing_options: dict):
    """Cache batch processing to avoid recomputation."""
    results = []
    for file_id in file_ids:
        result = process_single_file(file_id, processing_options)
        results.append(result)
    return results
```

## 🔧 Configuration & Files

### Key Configuration Files
- **`pyproject.toml`**: Dependencies, optional extras, build configuration
- **`.ruff.toml`**: Linting rules (line length 120)
- **`.pre-commit-config.yaml`**: Code quality hooks
- **`CLAUDE.md`**: This AI assistant guide

### Optional Dependencies
```toml
[project.optional-dependencies]
# Performance
hiredis = ["hiredis>=3.0.0"]        # Faster Redis implementation
msgpack = ["msgpack>=1.0.0"]        # Fast binary serialization
dill = ["dill>=0.3.0"]             # Extended pickle support

# Data formats
bson = ["pymongo>=4.0.0"]           # MongoDB BSON
yaml = ["PyYAML>=6.0"]              # YAML support
cbor = ["cbor2>=5.0.0"]             # Concise Binary Object
cloudpickle = ["cloudpickle>=2.0.0"] # Enhanced pickle
```

## ⚡ Performance Tuning

### Optimization Recommendations
1. **Serializer Choice**: Use `msgpack` for binary data (fastest), JSON for text
2. **Cache Size**: Set appropriate `maxsize` values based on memory constraints
3. **Factory Pattern**: Always use `factory=lambda: redis.Redis()` for concurrent access
4. **Redis Client**: Consider `hiredis` for better performance
5. **TTL Strategy**: Use structure-level TTL for efficiency

### Memory Management
There is no byte-size (`max_size_mb`) limit; constrain the cache by item count
with `maxsize` on the constructor, and adjust `cache.maxsize` at runtime:

```python
# Size-constrained caching
cache = RedisFuncCache(__name__, LruPolicy, maxsize=1000, factory=factory)


@cache
def process_large_dataset(dataset: list, config: dict):
    """Process large datasets with item-count constraints."""
    return complex_processing(dataset, config)


# Dynamic sizing based on system memory (evaluated at construction;
# cache.maxsize remains settable afterwards)
def get_initial_maxsize():
    """Pick a starting cache size based on available memory."""
    import psutil

    memory = psutil.virtual_memory()
    return 500 if memory.percent > 80 else 2000


adaptive_cache = RedisFuncCache(__name__, LruPolicy, maxsize=get_initial_maxsize(), factory=factory)


@adaptive_cache
def memory_intensive_operation(data):
    """Operation with adaptive cache sizing."""
    return process_data(data)
```

## 🐛 Troubleshooting

### Common Error Messages

#### "Client type mismatch"
**Issue**: Using `redis.Redis` client with async cache
**Solution**: Use `aioredis` for async caches, `redis.Redis` for sync caches

```python
# ✅ Correct setup
import aioredis

async_cache = RedisFuncCache("my-async-cache", LruPolicy, factory=lambda: aioredis.from_url("redis://localhost"))

# ✅ Alternative sync setup
import redis

sync_cache = RedisFuncCache("my-sync-cache", LruPolicy, factory=lambda: redis.Redis(host="localhost", port=6379))
```

#### "Circular reference"
**Issue**: Older versions (≤ v0.8) kept a weakref back-reference from the policy to the cache
**Solution**: Since v0.9 the policy holds no reference at all — the cache copies `prefix`/`name` onto it at construction; nothing to handle

#### "Serialization failed"
**Issue**: Non-serializable function arguments
**Solution**: Use `excludes` parameter or ensure arguments are serializable

```python
# Exclude non-serializable fields (`excludes` is a decorator option)
@cache(excludes=["obj.file_handle", "obj.connection"])
def process_file(obj: FileObject):
    return obj.process()
```

#### "Lua script failed"
**Issue**: Redis connection or key distribution problems
**Solution**: Check Redis connectivity and cluster configuration

### Debugging Techniques

#### Enable Logging
```python
import logging

logging.basicConfig(level=logging.DEBUG)


# Monitor cache operations
@cache
def debug_function(x):
    print(f"Executing with {x}")  # Visible when cache misses
    return x * 2
```

#### Manual Cache Inspection
```python
# Check cache statistics (collected via stats_context)
cache = RedisFuncCache("my-cache", LruPolicy, factory=lambda: redis.Redis())


# Test specific scenarios
@cache
def test_func(x):
    print(f"Computing result for {x}")
    return x**2


with cache.stats_context() as stats:
    test_func(1)  # miss: executes the function
    test_func(1)  # hit: served from Redis

print(f"hits={stats.hit}, misses={stats.miss}")
```
