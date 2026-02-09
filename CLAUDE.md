# redis_func_cache

Python decorator library for caching function results in Redis - a distributed alternative to `functools.lru_cache`.

## Quick Start

```bash
# Install with dev dependencies
uv sync --all-groups --dev
# Or
pip install -e ".[all]" --group dev

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

# Build
pip install build
python -m build
```

## Architecture

- `src/redis_func_cache/cache.py` - Core RedisFuncCache class
- `src/redis_func_cache/policies/` - Cache eviction policies (LRU, FIFO, LFU, MRU, RR, LRU-T)
- `src/redis_func_cache/lua/` - Redis Lua scripts for atomic operations
- `src/redis_func_cache/mixins/` - Hash computation and script execution mixins

## Key Files

- `__init__.py` - Main exports (RedisFuncCache, policy classes)
- `pyproject.toml` - Dependencies, build config
- `.ruff.toml` - Line length 120, code style rules

## Code Style

- Type hints required throughout
- Ruff for linting/formatting (line length 120)
- MyPy for type checking
- Pre-commit hooks enforced

## Gotchas

- **v0.7+ breaking change**: Policies must be instantiated: `LruTPolicy()` not `LruTPolicy`
- Use factory pattern for concurrent scenarios, not direct client instances
- Default bytecode hashing makes caches incompatible across Python versions
- Functions with non-serializable args need `excludes` parameter
- Async cache requires async Redis client and async functions
- All operations use Lua scripts for atomicity (dual data structures: sorted set + hash)
