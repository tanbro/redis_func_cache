# ADR 0001: Eviction Policy Roadmap Beyond LRU/LRU-T/LFU

- **Status:** Accepted (direction agreed; the first implementation ADR has
  landed — see ADR 0002)
- **Date:** 2026-09-29
- **Deciders:** maintainers

## Context

Every eviction policy in _redis-func-cache_ is a composition of `Keying`, `Hasher`,
and `Scripts`, and its entire decision logic lives in the score it assigns inside a
single ZSET (`...:0`) that pairs with the value HASH (`...:1`). Get/put are atomic
Lua scripts, `calc_ext_args` can inject extra ARGV into put (MRU already reuses the
LRU scripts this way), and the Lua layer can see the serialized value itself
(`ARGV[5]`) — so a put script can score by value size, something most local caches
cannot do.

Constraints that shape any new policy:

- Policies are stateless; presets take no arguments. All state must live in Redis.
- The index structure is one ZSET (or SET for RR) next to one HASH. Changing the
  key-pair layout is a breaking, golden-test-pinned change.
- Lua is single-threaded per script: per-access cost must stay O(log N); anything
  that needs sketch data structures or O(N) scans per operation is out.

LRU/LRU-T (the current defaults) have two well-documented blind spots: they are
frequency-blind (one-off accesses evict hot entries — scan pollution) and
size-blind (a 10 MB result costs the same slot as a 10 B result). LFU's classical
weakness is the inverse: stale hot entries never age out.

## Decision

Extend the policy family along three accepted directions, ranked by
value-per-effort, and explicitly reject three candidates. All accepted policies
reuse the existing key-pair layout, get/put script architecture, and preset matrix
(`{policy} × {Single,Multiple,Cluster,ClusterMultiple}Keying`); none change the
cache-layer API or the put ARGV contract beyond optional `calc_ext_args` extensions.

### Accepted

1. **Hyperbolic / LFU-with-aging** — score = `log(frequency) / age^d` (d ≈ 0.25),
   recomputed on each access inside the get/put scripts
   (Hyperbolic Caching, USENIX ATC 2020). Captures recency _and_ frequency in one
   ZSET score, ages out stale hot entries without a decay task. Purely a
   score-formula change; the cheapest real win. This addresses LFU's aging flaw
   using the same ZSET mechanism LFU already uses.
   _Implementation ADR: [ADR 0002](0002-hyperbolic-eviction-policy.md)._
2. **GDSF (Greedy-Dual-Size)** — score = `frequency × call_cost / value_size`
   (Cao & Irani 1997; Young's greedy-dual framework). Value size is computed in
   Lua from `ARGV[5]`; call cost arrives as an extra ARGV via `calc_ext_args`,
   declared per-function by the user. Theoretically dominates LRU when sizes or
   costs are heterogeneous — which is the norm for function-result caching.
   _Implementation ADR: TBD._
3. **Random admission (admission-only variant)** — do not change eviction; on put
   (insert branch only), admit a new entry by a cheap stochastic rule (e.g. reject
   with probability p, or reject when a small recent-rejection record says the key
   was just evicted). Encodes the core W-TinyLFU insight that _admission_
   decisions, not eviction upgrades, neutralize scan pollution. A few lines of
   Lua; can be layered on LRU-T or any other base policy.
   _Implementation ADR: TBD._

### Deferred

1. **SLRU (segmented LRU)** — probational + protected segments; requires either a
   second index ZSET (four-key pair) or score-space partitioning within one ZSET.
   Good pollution resistance (strong baseline in the LRU-K literature) but the
   layout/complexity cost is not justified until the accepted policies above prove
   insufficient.
2. **LRU-K / LRU-2** — the most theoretically grounded anti-pollution policy
   (O'Neil et al. 1993), but needs a per-entry "previous access time" metadata
   field in the HASH and an extra round-trip inside the get script. Revisit if
   admission + Hyperbolic do not hold up in practice.

### Rejected

- **ARC** — ghost lists double the key-pair layout; measured improvements over LRU
  are marginal and contested.
- **TinyLFU / CacheLib-style sketches** — Count-Min Sketch + sparse structures are
  not implementable performantly in Lua; per-access cost would violate the
  single-atomic-script design goal. The admission insight is captured instead by
  the accepted random-admission variant.
- **Clock / second chance** — a circular hand has no efficient Redis primitive
  inside Lua; a faithful simulation is O(N) per put.

## Consequences

- **Positive:** the two real blind spots of the default policies (frequency,
  size/cost) each get a theoretically backed fix that costs only a score formula
  and, for GDSF, one optional ARGV; scan pollution gets an admission-level fix
  that no eviction upgrade provides.
- **Neutral:** naming follows the existing pattern (`HyperbolicPolicy` /
  `GdsfPolicy` etc. × keying variants); LRU-T keeps its name (T = time-stamp-based
  ordering, documented — see quickstart), since renaming would break the public
  API for negligible benefit.
- **Negative / watch-outs:** score formulas that mix timestamps and frequencies
  must handle clock resets (Redis server TIME is authoritative, not client
  clocks); GDSF's value-size scoring makes hit rate sensitive to serializer
  choice; random admission makes hit rates nondeterministic, so its tests need
  statistical rather than exact assertions.
- Any new put-script ARGV must land at the `ext_args` position (ARGV[7] onward)
  per the put ARGV contract; the golden ARGV layout tests must be extended in the
  same change.

## References

- Berger et al., _Hyperbolic Caching_, USENIX ATC 2020.
- Cao & Irani, _Cost-Aware WWW Proxy Caching Algorithms_, USENIX 1997.
- Young, _On-line File Caching_, SODA 1998.
- O'Neil et al., _The LRU-K Page Replacement Algorithm_, SIGMOD 1993.
- Eisenman et al. / Yang et al., _W-TinyLFU_ (rapidash sketch admission), and
  _SIEVE is Simpler than LRU_, NSDI 2024 (eviction-side alternative, not adopted
  here because it needs a per-entry visited bit).
