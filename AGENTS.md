# AI AGENT Programming Instructions for redis_func_cache Project

## 🎯 AI Assistant Quick Start

### Project Overview
A Python Redis-based function caching library with decorator-based API, supporting multiple eviction policies and async/sync operations. Designed for high-performance caching with atomic operations.

### Essential Architecture Concepts
- **Strategy Pattern**: Pluggable eviction policies (LRU, LFU, FIFO, MRU, RR)
- **Dual Redis Structure**: ZSET (scoring) + HASH (storage) with atomic Lua operations
- **Mixin Composition**: HashMixin + ScriptMixin for policy behavior

### Critical API Rules (v0.7+)
```python
# ❌ WRONG (deprecated)
@cache(policy=LruTPolicy)

# ✅ CORRECT (instance required)
@cache(policy=LruTPolicy())

# ❌ NOT thread-safe
cache = RedisFuncCache(client=redis_client)

# ✅ Thread-safe for concurrent use
cache = RedisFuncCache(factory=lambda: redis.Redis())
```

## 🔍 Key Information Index

### Quick File References
- **Core Implementation**: `src/redis_func_cache/cache.py` - Main class (`exec`, `aexec`, `decorate` methods)
- **Policies**: `src/redis_func_cache/policies/` - All eviction policy implementations
- **Redis Structure**: Keys with `:0` suffix = ZSET, `:1` suffix = HASH
- **Lua Scripts**: `src/redis_func_cache/lua/` - Atomic operations on both structures
- **Serialization**: `src/redis_func_cache/mixins/hash.py` - JSON/pickle/msgpack options
- **Errors**: `src/redis_func_cache/exceptions.py` - Custom exceptions

### Common Issues to Flag
1. **Policy Instantiation**: Must use `LruTPolicy()` not `LruTPolicy`
2. **Bytecode Sensitivity**: Default hash includes function bytecode → cross-version issues
3. **Client Mismatch**: Async cache requires `aioredis`, sync cache requires `redis.Redis`
4. **Circular References**: Policies use weakref to cache to prevent cycles

### Directory Structure
```
Core Components:
├── src/redis_func_cache/cache.py          # RedisFuncCache class
├── src/redis_func_cache/__init__.py       # Public API exports
├── src/redis_func_cache/policies/         # Policy implementations
├── src/redis_func_cache/mixins/           # HashMixin + ScriptMixin
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

### Mixin Architecture
- **HashMixin**: Handles serialization (JSON/pickle/msgpack) and key hashing
- **ScriptMixin**: Manages Lua script loading and execution
- **Policy Implementation**: Uses multiple inheritance from both mixins

### API Usage Patterns

#### Correct API Usage (v0.7+)
```python
# ✅ Policy instantiation (required)
@cache(policy=LruPolicy())

# ✅ Thread-safe cache creation
import redis
cache = RedisFuncCache(factory=lambda: redis.Redis())

# ✅ Async cache setup
import aioredis
async_cache = RedisFuncCache(factory=lambda: aioredis.from_url("redis://localhost"))
```

#### Important Rules
- **Async vs Sync**: Async cache requires `aioredis`, sync requires `redis.Redis`
- **Type Safety**: Client type mismatches are checked at runtime
- **Cannot Mix**: Don't use sync functions with async cache (and vice versa)

## 🚨 Common Anti-patterns

### Critical Architecture Issues
- **Circular References**: Policies use `weakref` to cache to prevent cycles
- **Bytecode Sensitivity**: Default hash includes bytecode → cross-version incompatibility
- **Cache Stampede**: Multiple threads may execute same function on cache miss
- **Serialization Failures**: Non-serializable args need `excludes` parameter

### Redis Integration Issues
- **Cluster Compatibility**: Regular policies fail in cluster - use `*ClusterPolicy`
- **Dual Structure**: ZSET + HASH must be maintained together
- **TTL Modes**: Structure-level (default) vs per-item (Redis 7.4+)

### Usage Pattern Issues

#### Bytecode Sensitivity Problem
```python
# ❌ Cache version-specific (function bytecode changes between versions)
@cache(policy=LruPolicy())
def expensive_func(x): ...

# ✅ Cross-version compatible
@cache(
    policy=LruPolicy(),
    exclude_bytecode=True
)
def expensive_func(x): ...
```

#### Serialization Issues
```python
# ❌ Non-serializable arguments
class Unserializable:
    def __init__(self):
        self.file_handle = open("file.txt")

# ✅ Exclude problematic fields
@cache(policy=LruPolicy(), excludes=["obj.file_handle"])
def process_data(obj: Unserializable):
    ...
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
**Jobs**: Cross-platform testing (Linux 3.9-3.14, macOS), code quality, PyPI release
**Note**: Windows CI disabled for focused testing

## 📊 Serialization Options

### Default: JSON (Recommended for safety)
```python
from redis_func_cache import LruPolicy

# Standard JSON serialization
@cache(policy=LruPolicy())
def compute_data(x):
    return {"result": x * 2}
```

### Performance Optimized Serializers
```python
# Fastest for binary data (recommended for embeddings)
@cache(policy=LruPolicy(serializer="msgpack"))
def compute_data(x):
    return x * 2

# Extended pickle support
@cache(policy=LruPolicy(serializer="dill"))
def compute_data(x):
    return x * 2

# MongoDB compatibility
@cache(policy=LruPolicy(serializer="bson"))
def compute_data(x):
    return x * 2
```

## 💡 Caching Strategies & Patterns

### Performance-Critical Operations
Cache expensive computations to improve response times and reduce resource usage.

#### API Call Caching
```python
import redis
from redis_func_cache import LruPolicy

# Cache expensive external API calls
@cache(policy=LruPolicy(maxsize=1000, ttl=3600))
def fetch_api_data(endpoint: str, params: dict):
    """Cache API responses to reduce rate limits and costs."""
    response = requests.get(endpoint, params=params)
    return response.json()

# Use with cross-version compatibility
@cache(
    policy=LruPolicy(maxsize=500),
    exclude_bytecode=True
)
def api_call_with_retry(params: dict):
    """API calls with retry logic."""
    return fetch_api_data("/api/endpoint", params)
```

#### Data Processing Caching
```python
# Cache complex computations
@cache(policy=LruPolicy(maxsize=500))
def process_large_dataset(data: list, config: dict):
    """Cache expensive data processing operations."""
    processed = []
    for item in data:
        result = apply_transformations(item, config)
        processed.append(result)
    return processed

# Cache text preprocessing
@cache(
    policy=LruPolicy(maxsize=1000),
    exclude_bytecode=True
)
def preprocess_text(text: str, cleaning_rules: dict):
    """Cache text cleaning operations."""
    cleaned = text.lower()
    if 'remove_punctuation' in cleaning_rules:
        cleaned = re.sub(r'[^\w\s]', '', cleaned)
    return cleaned
```

### Advanced Caching Patterns

#### Multi-Parameter Caching
```python
# Cache with multiple parameters for granular control
@cache(
    policy=LruMultiplePolicy(maxsize=1000),
    exclude_bytecode=True
)
def complex_calculation(input_data: str, algorithm: str, version: int):
    """Cache different algorithm variations separately."""
    return apply_algorithm(input_data, algorithm, version)
```

#### Time-Based Invalidation
```python
# Cache with automatic expiration for time-sensitive data
@cache(
    policy=LruPolicy(maxsize=1000, ttl=300),  # 5 minutes
    exclude_bytecode=True
)
def get_market_data(symbol: str):
    """Cache market data with automatic refresh."""
    return market_api.get_current_data(symbol)
```

#### Memory-Constrained Environments
```python
# Limit cache size for memory management
@cache(
    policy=LruPolicy(maxsize=200),
    serializer="msgpack",
    max_size_mb=10
)
def process_large_file(file_path: str, processing_options: dict):
    """Process large files with memory limits."""
    return process_file(file_path, processing_options)
```

### Cache Monitoring & Optimization

#### Performance Tracking
```python
from redis_func_cache import RedisFuncCache
import time

# Create cache with monitoring
cache = RedisFuncCache(
    factory=lambda: redis.Redis(),
    policy=LruPolicy(maxsize=1000)
)

def monitor_cache_performance():
    """Track cache hit rates and effectiveness."""
    while True:
        hits = cache.get_cache_hits()
        misses = cache.get_cache_misses()
        hit_rate = hits / (hits + misses) if (hits + misses) > 0 else 0

        print(f"Cache Hit Rate: {hit_rate:.2%}")
        print(f"Hits: {hits}, Misses: {misses}")

        # Adjust cache size based on performance
        if hit_rate < 0.5:  # Low hit rate
            cache.policy.maxsize = min(cache.policy.maxsize * 2, 5000)

        time.sleep(60)
```

### Caching Best Practices

1. **Selective Caching**: Cache only expensive operations (compute time > cache lookup time)
2. **Appropriate TTLs**: Use TTL for time-sensitive data, None for static data
3. **Size Management**: Set reasonable maxsize values based on available memory
4. **Serialization Choice**: Use msgpack for binary data, JSON for human-readable data
5. **Cross-Version Compatibility**: Use `exclude_bytecode=True` for shared environments
6. **Error Handling**: Plan for cache failures gracefully

### Common Anti-patterns

```python
# ❌ Cache trivial operations (overhead > benefit)
@cache(policy=LruPolicy())
def simple_addition(x, y):
    return x + y

# ✅ Cache expensive operations
@cache(policy=LruPolicy(maxsize=100))
def complex_ml_inference(data):
    return model.predict(data)

# ❌ No expiration for time-sensitive data
@cache(policy=LruPolicy())
def get_exchange_rate(from_currency, to_currency):
    return forex_api.get_rate(from_currency, to_currency)

# ✅ Appropriate expiration
@cache(policy=LruPolicy(ttl=300))  # 5 minutes
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
# Cache external API responses
@cache(
    policy=LruPolicy(maxsize=2000, ttl=3600),
    exclude_bytecode=True
)
def fetch_weather_data(city: str, units: str = "metric"):
    """Cache weather API responses to reduce rate limits."""
    return weather_api.get_current_weather(city, units)
```

#### Data Processing Pipeline
```python
# Cache complex data transformations
@cache(
    policy=LruMultiplePolicy(maxsize=1000),
    serializer="msgpack"
)
def process_financial_data(raw_data: dict, analysis_config: dict):
    """Cache financial analysis results."""
    return analyze_data(raw_data, analysis_config)
```

#### Batch Processing
```python
# Cache batch processing results
@cache(
    policy=LruPolicy(maxsize=500, ttl=7200),
    exclude_bytecode=True
)
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
```python
# Size-constrained caching
@cache(
    policy=LruPolicy(maxsize=1000),
    max_size_mb=50  # Limit total cache size
)
def process_large_dataset(dataset: list, config: dict):
    """Process large datasets with memory constraints."""
    return complex_processing(dataset, config)

# Dynamic sizing based on system memory
def get_adaptive_policy():
    """Adjust cache size based available memory."""
    import psutil
    memory = psutil.virtual_memory()
    if memory.percent > 80:
        return LruPolicy(maxsize=500)
    return LruPolicy(maxsize=2000)

@cache(policy=get_adaptive_policy())
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
async_cache = RedisFuncCache(
    factory=lambda: aioredis.from_url("redis://localhost")
)

# ✅ Alternative sync setup
import redis
sync_cache = RedisFuncCache(
    factory=lambda: redis.Redis(host="localhost", port=6379)
)
```

#### "Circular reference"
**Issue**: Policy holding direct reference to cache object
**Solution**: Policies use `weakref` internally - this is handled automatically

#### "Serialization failed"
**Issue**: Non-serializable function arguments
**Solution**: Use `excludes` parameter or ensure arguments are serializable

```python
# Exclude non-serializable fields
@cache(policy=LruPolicy(), excludes=["obj.file_handle", "obj.connection"])
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
@cache(policy=LruPolicy())
def debug_function(x):
    print(f"Executing with {x}")  # Visible when cache misses
    return x * 2
```

#### Manual Cache Inspection
```python
# Check cache contents
cache = RedisFuncCache(factory=lambda: redis.Redis())
print(f"Cache hits: {cache.get_cache_hits()}")
print(f"Cache misses: {cache.get_cache_misses()}")

# Test specific scenarios
@cache(policy=LruPolicy())
def test_func(x):
    print(f"Computing result for {x}")
    return x ** 2
```
