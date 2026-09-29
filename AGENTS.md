# AGENTS.md — guidance and constraints for coding agents

redis_func_cache: a Python library caching function results in Redis via a decorator, with pluggable
eviction policies and sync/async support. User-facing documentation lives in `docs/` — write usage
questions and examples there, never duplicate it here.

## Architecture (read this before touching src/)

`Policy(keying, hasher, scripts)` — three orthogonal components composed into a policy. Ownership
rule: **declaration lives in Scripts, actions live in Policy, the cache layer only talks to the
Policy**:

- **Keying** (`src/redis_func_cache/keying.py`): key naming. Four variants
  (`SingleKeying` / `MultipleKeying` / `ClusterSingleKeying` / `ClusterMultipleKeying`). Cluster
  variants hash-tag the varying segment (`{...}`) so both keys of a pair share a slot. Stateless:
  namespace (`prefix`, `name`) is passed to each call, not stored.
- **Hasher** (`src/redis_func_cache/hashing.py`, `fingerprint.py`): computes the per-call sub-key
  from function + args via `HashConfig` (algorithm, serializer, `use_bytecode`). A set of presets
  plus a `make_hasher` factory. The fingerprint is md5(fullname + bytecode); checksums are base64
  digests. Pure computation — no Redis IO.
- **Scripts** (`src/redis_func_cache/scripts.py`): pure **declaration + registration** — the
  get/put Lua file names (`src/redis_func_cache/lua/`), the index structure
  (`zset` for most policies, `set` for RR), `calc_ext_args` (extra ARGV values appended to put,
  MRU → `("mru",)`), `register_scripts`/`register_vacuum_script` (per-client registration cached
  in a `WeakKeyDictionary`), and the module-level ARGV builders `build_get_args`/`build_put_args`.
  Scripts never invokes the scripts and never computes key names.
- **Policy** (`src/redis_func_cache/policies/__init__.py`): the **single entry point from the cache
  layer** — `get/put/aget/aput` (register + ARGV assembly + invoke), `vacuum_all_pairs`/`avacuum_all_pairs` +
  `vacuum_one_pair`/`avacuum_one_pair` (cursor loop),
  `get_size/aget_size` (ZCARD/SCARD dispatch on `Scripts.index_structure`),
  `purge_all_pairs`/`apurge_all_pairs` + `purge_one_pair`/`apurge_one_pair`, `calc_key_pair`/`calc_hash`,
  `iterate_key_pairs` (the last three are the user
  introspection surface; the cache layer itself only calls `locate` — the single identity-assembly
  point — plus get/put and the maintenance methods, reusing the located identity via the `located`
  kwarg). Also stateless: `prefix` /
  `name` are explicit parameters on every method that needs them (mirroring Keying), so preset
  instances are shareable singletons — never copy a policy, never reintroduce `_bind`.
- **Naming rule for maintenance methods**: suffixes (`_all_pairs`/`_one_pair`) appear only on the
  layer where the granularity contrast exists — the policy and its keying component both use the
  explicit names (`Keying.purge_all_pairs` is the semantic source; `Policy.purge_all_pairs` is a
  thin forwarder); the cache
  facades keep the short names `purge`/`vacuum` (whole-cache granularity only; no one-pair cache
  facade by design — a fn-keyed one-pair op would be a false promise under `MultipleKeying`,
  whose entries span several pairs).
- **IO ownership follows each component's abstraction** (Redis IO is *not* exclusive to Policy):
  Keying owns key-lifecycle IO (enumerating/deleting the key pairs it names — only it knows the
  layout, e.g. `MultipleKeying.purge_all_pairs`'s SCAN+UNLINK); Policy owns entry-level IO (get/put/vacuum/
  get_size — it orchestrates keying + hasher + scripts); Hasher and Scripts are pure. "Single entry
  point" means the cache layer only talks to Policy — not that only Policy touches Redis.
- `policies/` holds presets only: `Policy` instances named `{Lru,LruT,Fifo,FifoT,Lfu,Mru,Rr} ×
  {(none),Multiple,Cluster,ClusterMultiple}`. Presets take **no arguments**; they are pre-composed.

Data layout: every cache function gets a key pair — `:0` suffix = ZSET (or SET for RR) index with
eviction scores, `:1` suffix = HASH of `hash_value → serialized result`. Get/put/vacuum are single
atomic Lua scripts.

### Put ARGV contract

`build_put_args` in `scripts.py` builds
`args = (maxsize, int(update_ttl), ttl, hash_value, value, field_ttl, *ext_args, encoded_options)`.
So **`ext_args` must land on ARGV[7]** and the reserved options JSON goes last. `Policy.put`
assembles it. `tests/test_golden.py::TestGoldenArgvLayout` pins this (both the pure functions and
an end-to-end pass through every preset). If you reorder put arguments, Lua scripts and that test
must change together.

## Hard API invariants (break = bug)

- `RedisFuncCache(name, policy=lru_t_policy, *, redis_client=None, factory=None, maxsize=DEFAULT_MAXSIZE,
  ttl=DEFAULT_TTL, update_ttl=True, ignore_redis_errors=False, prefix=DEFAULT_PREFIX,
  serializer="json", handler=None)` (see the `RedisFuncCache.__init__` in `cache.py`). The decorator returned by `cache(...)` accepts only `serializer`, `excludes`, `ttl`,
  `update_ttl`, `write_only`, and never `policy` — unknown kwargs are forwarded to the Lua script
  and fail at runtime.
- Policies are argument-less instances passed positionally to the constructor. `maxsize`, `ttl`,
  `serializer` are `RedisFuncCache(...)` options; `cache.maxsize` is settable at runtime.
- The policy is stateless: no back-reference to the cache, no stored namespace. `prefix`/`name`
  are explicit per-call parameters on Policy methods (the constructor stores the instance as-is,
  no copy, no `_bind`). Presets are shared singletons; tests may assert `cache.policy is preset`.
- Sync cache requires a sync client (`redis.Redis`), async requires `redis.asyncio.Redis`; mixing
  raises `TypeError`. Exception convention: wrong-type arguments → `TypeError`; state problems →
  `RuntimeError`. Follow it for new guards.
- Bytecode is part of the default fingerprint by design — a Python upgrade invalidates stale keys
  (documented in `docs/usage/considerations.md`). Do not add an opt-out knob to built-in policies;
  users compose a custom policy instead.
- `make_bound` (`cache.py`) anchors both exclude filters on `signature(fn).bind(*args, **kwds)`:
  `excludes` matches named parameter slots plus `**kwargs` keys; `excludes_positional` indexes the
  **expanded positional stream** (`bound.args`; keyword-only params never occupy an index, varargs
  are addressed element-wise). Never index `bound.arguments` by enumeration order and never exclude
  a catch-all (`*args`/`**kwargs`) parameter as a whole — both collapse the hash to function
  identity, i.e. silent wrong-result cache hits (pinned by `tests/test_excludes.py`).
- Golden fixtures (`tests/_golden.json`) template checksums as `{checksum_a}` / `{checksum_b}`
  placeholders; digests are re-derived in the test, never frozen. Regenerate with
  `tests/_gen_golden.py`. If a fixture failure mentions bytecode, fix the templating, not the pin.

## Development commands

```bash
uv sync --all-extras --dev          # install (optional extras are needed by the test suite)
cd docker && docker compose up -d   # Redis standalone + cluster for tests
uv run pytest -xv --cov             # REDIS_URL defaults to redis://
REDIS_CLUSTER_NODES="127.0.0.1:6379 ..." uv run pytest   # enables cluster test groups
uv run ruff check --fix && uv run ruff format
uv run mypy
uv run pre-commit run -a
```

- `uv run --python X` rebuilds `.venv` **without** optional extras; follow it with
  `uv sync --all-extras --dev` or serializer tests fail with "Unknown serializer".
- Dependency floors in `pyproject.toml` mean "oldest version we have verified", not "oldest API
  that could work". Extras carry no upper bounds; the `redis` dependency is capped `<9`.

## Process constraints

- Branching: work on `develop`; releases merge `develop` → `main` and tag **on `main` only**
  (format `v1.0.a1`; hatch-vcs derives the version from the tag). CI runs on pushes/PRs to `main`
  and on tags — a green `develop` proves nothing, do not infer CI status from it.
- Never run release steps (tag, push to shared refs) or destructive git operations without the
  user's explicit confirmation of the target ref.
- Pre-commit may reformat files mid-commit: if the hook reports fixes, re-add and re-commit.
- Test framework is pytest (+ pytest-asyncio); no stdlib `unittest`. Match the existing patterns in
  `tests/` (`_catches.py` CACHES fixtures, `_mocks.patch_object`); expiry is simulated via
  `hdel`/`delete`, tests do not require Redis ≥ 7.4.
- Security issues go through GitHub private vulnerability reporting (see `SECURITY.md`) — never
  open a public issue for them.

## Known sharp edges

- Two Redis structures must stay consistent: put scripts HDEL evicted fields in batches (≤4000 per
  `unpack`) to avoid Lua memory limits on mass eviction; vacuum (`vacuum.lua`) must type-check
  KEYS[1] before scanning (RR uses a SET, others a ZSET — WRONGTYPE otherwise).
- Field-level TTL (`ttl` on the decorator, HEXPIRE in Lua) requires Redis ≥ 7.4 and emits a
  UserWarning; structure-level `ttl` on the constructor is the portable option.
- A single shared client instance is not thread-safe for concurrent use; the factory must return
  lightweight clients sharing one pre-built pool (`redis.Redis.from_pool(pool)`), never build a
  pool per call (leaks connections, defeats EVALSHA).
- `uv.lock` is gitignored; `src/redis_func_cache/_version.py` is generated (do not commit).
