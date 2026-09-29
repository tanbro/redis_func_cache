# ADR 0004: Random admission policy (lru_tr)

- Status: Accepted
- Date: 2026-09-29
- Part of the [eviction policy roadmap](0001-eviction-policy-roadmap.md) (design recorded in map ticket [Random admission：准入规则与分层机制设计](https://github.com/tanbro/redis_func_cache/issues/18); implementation in [#19](https://github.com/tanbro/redis_func_cache/issues/19))

## Context

The roadmap's third accepted policy targets scan pollution: one pass of one-time keys evicting a cache's working set. The roadmap's thesis (following W-TinyLFU) is that _admission_ decisions — not eviction upgrades — neutralize this. Two design points were open: the admission rule itself, and how the mechanism composes with base policies under the stateless-policy constraint.

## Decision

- **Admission rule: fixed rejection probability `p`.** A new insertion is rejected with probability `p` (the put script returns 0 without writing); an entry already present in the index is **always admitted** — an update must never be dropped, or a hot entry's refresh could be lost and the cache would keep serving the stale value. Rejection is invisible to the caller: no error, an evicted-count of 0.
  A recent-rejection ("ghost") record was rejected for now: it needs a capacity-bounded ordered structure, which does not fit the fixed `:0`/`:1` key pair (a companion field à la `:m` solves the layout but not the bounded eviction — a HASH has no ordered removal, and HEXPIRE would pin Redis ≥ 7.4 without bounding capacity). Deferred until the fixed-`p` baseline proves insufficient.
- **Composition: a Scripts-level composable piece, not N script copies.** `RandomAdmissionScripts(base_scripts, p=0.5)` (exported from `redis_func_cache.scripts`) prefixes the base put script, at load time, with a small Lua prologue: it checks index membership with the command matching the base's `index_structure` (ZSCORE for zset policies, SISMEMBER for the SET-based RR family) and, on a miss, rejects with probability `p`. The check must live inside the composed Lua script — whether a call is an insert or an update is only known to the script; deciding in Python would need an extra round-trip per put and race with it. `calc_ext_args` delegates to the base, so any base policy's ARGV contract is preserved.
- **`p` defaults to 0.5 and is a constructor parameter of the composable piece**, baked into the composed script source. It is deliberately not on the ARGV channel: unlike GDSF's `cost` (a per-function property), the admission probability is a deployment-side taste, constant per cache. Presets are argument-less and bake `p = 0.5`; a user composing custom policies can pass any `p` in `[0, 1]` (out-of-range or NaN raises `ValueError`; non-numeric input propagates `float()`'s error).
- **Preset family: LRU-T only** — `lru_tr_policy` / `lru_tr_multiple_policy` / `lru_tr_cluster_policy` / `lru_tr_cluster_multiple_policy`. LFU/GDSF already carry frequency-based scan resistance and RR evicts randomly, so admission on top of them buys little; LRU-T is the classical scan-pollution victim the W-TinyLFU literature addresses. `RandomAdmissionScripts` is public for composing over other bases. The name reads "LRU-T, Random admission" (base first, modifier after, matching `lru_t`); the W-TinyLFU name was rejected as an overclaim — that design includes a Count-Min Sketch and an SLRU stage we do not have.
- **Redis ≥ 7.0 requirement, documented not enforced.** The prologue uses Lua `math.random`, which is seeded per script execution from Redis 7.0 on; on older servers the sequence would be deterministic across runs (all replays would make the same decisions). This is documented in `docs/usage/considerations.md`.

## Theoretical standing

`lru_tr` is positioned as the **cheap baseline of scan-resistant admission**, not an approximation of W-TinyLFU's hit rates:

- Einziger, Friedman & Manes, _TinyLFU_, ACM TOCS 2017 — admission filtering (not eviction) is the mechanism against pollution; the filter's quality is a free parameter of that analysis, and a coin flip is its lowest point.
- A one-pass scan of length S evicts an expected `p·S` pre-existing entries (each scanned key is admitted with probability `p`) — the damage is capped by `p` regardless of scan length, while hot entries are protected by the unconditional update path.
- Jaleel et al., _RRIP_, ISCA 2010 — randomized insertion is an established cheap scan-resistant baseline in the CPU-cache insertion-policy literature.

## Consequences

- **Positive:** anti-scan-pollution admission at near-zero cost — no new Lua files, no index or key-layout changes, ARGV contract untouched (golden tests extended with the new presets automatically); composable over every built-in policy family.
- **Negative:** hit rates become nondeterministic (statistical test assertions only); a rejected insertion wastes one function invocation's result (the call itself still succeeds and the next call re-invokes the function); requires Redis ≥ 7.0.
- **Neutral:** the composed put script is not a package resource — `put_script` still names the base file whose text the prologue prefixes; the golden fixture pins the base file names.

## References

- Einziger, Friedman & Manes, _TinyLFU: A Fresh Look at Power-Law Key Distribution and the I/O Cost of Flash_, ACM TOCS 2017.
- Eisenman et al. / Yang et al., _W-TinyLFU_ (admission principle; sketch-based filters are the heavyweight direction if this baseline proves insufficient).
- Jaleel et al., _High Performance Cache Replacement Using Re-Reference Interval Prediction (RRIP)_, ISCA 2010.
