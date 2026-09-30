# ADR 0004: Random admission policy (lru_tr)

- Status: Accepted
- Date: 2026-09-29
- Part of the [eviction policy roadmap](0001-eviction-policy-roadmap.md) (design recorded in map ticket [Random admission：准入规则与分层机制设计](https://github.com/tanbro/redis_func_cache/issues/18); implementation in [#19](https://github.com/tanbro/redis_func_cache/issues/19))

## Context

The roadmap's third accepted policy targets scan pollution: one pass of one-time keys evicting a cache's working set. The roadmap's thesis (following W-TinyLFU) is that _admission_ decisions — not eviction upgrades — neutralize this. Two design points were open: the admission rule itself, and how the mechanism composes with base policies under the stateless-policy constraint.

## Decision

- **Admission rule: fixed rejection probability `p`.** A new insertion is rejected with probability `p` (the put script returns 0 without writing); an entry already present in the index is **always admitted** — an update must never be dropped, or a hot entry's refresh could be lost and the cache would keep serving the stale value. Rejection is invisible to the caller: no error, an evicted-count of 0.
  A recent-rejection ("ghost") record was rejected for now: it needs a capacity-bounded ordered structure, which does not fit the fixed `:0`/`:1` key pair (a companion field à la `:m` solves the layout but not the bounded eviction — a HASH has no ordered removal, and HEXPIRE would pin Redis ≥ 7.4 without bounding capacity). Deferred until the fixed-`p` baseline proves insufficient.
- **Composition: a dedicated Lua script, not N copies and not string composition.** `lru_tr_put.lua` is the LRU-T put script plus one contiguous admission block in the insertion branch (admission is checked _before_ eviction, so a rejected insertion never evicts anything); reads reuse `lru_t_get.lua` unchanged. The check must live inside the Lua script — whether a call is an insert or an update is only known to the script; deciding in Python would need an extra round-trip per put and race with it. An earlier revision of this ADR specified load-time string composition of a prologue over arbitrary base scripts; review rejected it — composed Lua is invisible to static tooling and the generic composability bought nothing, since admission only pairs meaningfully with LRU-T (LFU/GDSF carry frequency resistance, RR evicts randomly). A semantic drift guard pins the p=0 behavior of `lru_tr_put.lua` to be equivalent to `lru_t_put.lua`.
- **`p` is two-layered: baked default + per-function override.** `LruTrScripts(reject_p=0.5)` (in `redis_func_cache.scripts`) passes its baked probability as ARGV[7] (the extension-argument slot, unused by the LRU-T family); the `reject_p` decorator kwarg overrides it per function, resolved by `calc_ext_args` exactly like the GDSF `cost`: a non-numeric value propagates `float()`'s error and a value outside `[0, 1]` (or NaN) raises `ValueError` at call time — no fallback. The script itself just reads ARGV[7]; the options JSON channel stays unused. Documented caveat: under the single-key-pair variants a per-function `reject_p` skews the cross-function competition (lower p grabs more slots) — a feature and a hazard, like GDSF's `cost` × keying.
- **Preset family: LRU-T only** — `lru_tr_policy` / `lru_tr_multiple_policy` / `lru_tr_cluster_policy` / `lru_tr_cluster_multiple_policy`. LFU/GDSF already carry frequency-based scan resistance and RR evicts randomly, so admission on top of them buys little; LRU-T is the classical scan-pollution victim the W-TinyLFU literature addresses — admission is therefore an LRU-T-specific mechanism, not a general add-on. The name reads "LRU-T, Random admission" (base first, modifier after, matching `lru_t`); the W-TinyLFU name was rejected as an overclaim — that design includes a Count-Min Sketch and an SLRU stage we do not have.
- **Redis ≥ 7.0 requirement, documented not enforced.** The prologue uses Lua `math.random`, which is seeded per script execution from Redis 7.0 on; on older servers the sequence would be deterministic across runs (all replays would make the same decisions). This is documented in `docs/usage/considerations.md`.

## Theoretical standing

`lru_tr` is positioned as the **cheap baseline of scan-resistant admission**, not an approximation of W-TinyLFU's hit rates:

- Einziger, Friedman & Manes, _TinyLFU_, ACM TOCS 2017 — admission filtering (not eviction) is the mechanism against pollution; the filter's quality is a free parameter of that analysis, and a coin flip is its lowest point.
- A one-pass scan of length S evicts an expected `p·S` pre-existing entries (each scanned key is admitted with probability `p`) — the damage is capped by `p` regardless of scan length, while hot entries are protected by the unconditional update path.
- Jaleel et al., _RRIP_, ISCA 2010 — randomized insertion is an established cheap scan-resistant baseline in the CPU-cache insertion-policy literature.

## Consequences

- **Positive:** anti-scan-pollution admission at near-zero cost — one real, statically checkable Lua file; no index or key-layout changes; the ARGV contract extension (ARG[7] = baked p) reuses the standard ext_args slot; per-function override via the reserved options JSON.
- **Negative:** hit rates become nondeterministic (statistical test assertions only); a rejected insertion wastes one function invocation's result (the call itself still succeeds and the next call re-invokes the function); requires Redis ≥ 7.0; `lru_tr_put.lua` duplicates `lru_t_put.lua`'s body — drift is guarded by a semantic-equivalence test (identical outcomes with p = 0), not by text diffing.
- **Neutral:** admission is an LRU-T-specific mechanism, not a general add-on; `reject_p` in the options JSON of any other policy is silently ignored (custom kwargs are forwarded to the script, which never reads them).

## References

- Einziger, Friedman & Manes, _TinyLFU: A Fresh Look at Power-Law Key Distribution and the I/O Cost of Flash_, ACM TOCS 2017.
- Eisenman et al. / Yang et al., _W-TinyLFU_ (admission principle; sketch-based filters are the heavyweight direction if this baseline proves insufficient).
- Jaleel et al., _High Performance Cache Replacement Using Re-Reference Interval Prediction (RRIP)_, ISCA 2010.
