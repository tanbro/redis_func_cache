# AGENTS.md — guidance and constraints for coding agents

redis_func_cache: a Python library caching function results in Redis via a decorator, with pluggable
eviction policies and sync/async support. User-facing documentation lives in `docs/` — write usage
questions and examples there, never duplicate it here.

## Architecture

`Policy(keying, hasher, scripts)` composes three orthogonal components. Ownership rule:
**declaration lives in Scripts, actions live in Policy, the cache layer only talks to the Policy** —
via `locate` (the single identity-assembly point), get/put, and the maintenance methods, reusing the
located identity through the `located` kwarg.

- Keying: key naming. Hasher: per-call sub-key from function + args. Scripts: get/put Lua script
  declaration, index structure, `calc_ext_args`, ARGV builders. Hasher and Scripts are pure — no
  Redis IO.
- IO ownership follows each component's abstraction (Redis IO is _not_ exclusive to Policy):
  Keying owns key-lifecycle IO (it alone knows the key layout), Policy owns entry-level IO
  (get/put/vacuum/get_size).
- All policy components are stateless: `prefix`/`name` are explicit per-call parameters, presets are
  pre-composed argument-less shareable singletons. Never copy a policy, never reintroduce `_bind`
  (rejected by design decision).
- Maintenance-method naming: `_all_pairs`/`_one_pair` suffixes appear only where the granularity
  contrast exists (policy + keying); the cache facades keep the short `purge`/`vacuum`. No one-pair
  cache facade by design — a fn-keyed one-pair op would be a false promise under multiple keying.
- Data layout: each cached function owns a key pair — `:0` = index (ZSET; SET for RR) with eviction
  scores, `:1` = HASH of `hash_value → serialized result`. Get/put/vacuum are single atomic Lua
  scripts.

### Put ARGV contract

`ext_args` must land on ARGV[7] and the reserved options JSON goes last (see `build_put_args` in
`scripts.py`). Reordering put arguments means changing the Lua scripts and
`tests/test_golden.py::TestGoldenArgvLayout` together.

## Hard API invariants (break = bug)

- The decorator returned by `cache(...)` accepts only `serializer`, `excludes`, `ttl`, `update_ttl`,
  `write_only` — never `policy`; unknown kwargs are forwarded to the Lua script and fail at runtime.
- Policies are argument-less instances passed positionally; `maxsize`/`ttl`/`serializer` are cache
  options (`cache.maxsize` is settable at runtime).
- Sync cache requires a sync client, async requires an async client (mixing → `TypeError`).
  Exception convention: wrong-type arguments → `TypeError`; state problems → `RuntimeError`.
- Bytecode is part of the default fingerprint by design. Do not add an opt-out knob to built-in
  policies; users compose a custom policy instead.
- `make_bound` anchors both exclude filters on `signature(fn).bind(...)`: never index
  `bound.arguments` by enumeration order, never exclude a catch-all (`*args`/`**kwargs`) parameter
  as a whole — either collapses the hash to function identity, i.e. silent wrong-result cache hits
  (pinned by `tests/test_excludes.py`).
- Golden fixtures (`tests/_golden.json`) template checksums as placeholders, re-derived in the test —
  never frozen; regenerate with `tests/_gen_golden.py`. A fixture failure mentioning bytecode means
  fix the templating, not the pin.

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

- `uv run --python X` rebuilds `.venv` without optional extras; follow it with
  `uv sync --all-extras --dev` or serializer tests fail.
- Dependency floors mean "oldest version we have verified", not "oldest possible API"; the `redis`
  dependency is capped `<9`.

## Documentation diagrams

Rules for diagrams in Markdown docs (README.md, CONTRIBUTING.md, docs/):

- Never use ASCII-art to describe structure or flow; use Mermaid.
- Inline Mermaid blocks have no length limit. Split a block when it mixes
  multiple topics or abstraction levels, or when it stops reading as one
  mental unit. Use ~60 lines as a signal to re-examine the block, not as a
  rule: split at 55 if the structure demands it, keep 80 unsplit if it is one
  coherent picture.
- Externalize a diagram only when it is reused across documents or must render
  where Mermaid is not supported (PyPI README; `docs/` renders inline Mermaid
  via `sphinxcontrib.mermaid`). Layout per document
  directory `<dir>/`:
  - source of truth: `<dir>/diagrams/<name>.mmd` (Mermaid) or `.dot` (Graphviz);
  - rendered artifact: `<dir>/images/<name>.svg` — the **only** form embedded in
    Markdown (`![name](images/name.svg)`); never reference or paste the source
    in the document;
  - commit source and artifact together; a source change must be re-exported in
    the same commit.
- Export Mermaid with `mmdc` using the repo-root `mmdc.json` containing
  `{"htmlLabels": false}` — required so text renders in SVG-as-image (secure
  static mode); pin the mmdc version when regenerating.
- SVG is plain text and small — keep it in ordinary Git (no LFS); LFS is for
  real binaries (see `.gitattributes`).
- Do not introduce other diagram tools (no draw.io; PlantUML only as a last
  resort when Mermaid truly cannot express the UML, exported to SVG the same
  way).

## Process constraints

- Branching: work on `develop`; releases merge `develop` → `main` and tag **on `main` only**
  (hatch-vcs derives the version from the tag). CI runs on pushes/PRs to `main` and on tags — a
  green `develop` proves nothing. Every push to `main` triggers the full pipeline: accumulate work
  on `develop`, merge in batches.
- Never run release steps (tag, push to shared refs) or destructive git operations without the
  user's explicit confirmation of the target ref.
- Pre-commit may reformat files mid-commit: re-add and re-commit. Three `language: system` hooks
  need host tools (uv, Node.js, lua-language-server) — setup details in CONTRIBUTING.md.
- Tests are pytest (+ pytest-asyncio), no stdlib `unittest`; follow the existing patterns in
  `tests/`.
- Security issues go through GitHub private vulnerability reporting (see `SECURITY.md`) — never a
  public issue.

## Known sharp edges

- Lua `unpack` overflows above ~4000 values: put scripts HDEL evicted fields in batches; and
  `vacuum.lua` must type-check KEYS[1] before scanning (RR uses a SET, others a ZSET).
- Field-level TTL (the decorator `ttl`, HEXPIRE) requires Redis ≥ 7.4 and emits a UserWarning;
  constructor-level `ttl` is the portable option.
- A shared client instance is not thread-safe for concurrent use; the factory must return
  lightweight clients sharing one pre-built pool, never build a pool per call.
- `uv.lock` is gitignored; `src/redis_func_cache/_version.py` is generated (do not commit).
