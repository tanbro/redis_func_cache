# ADR 0003: GDSF eviction policy

- Status: Accepted
- Date: 2026-09-29
- Part of the [eviction policy roadmap](0001-eviction-policy-roadmap.md) (decision recorded in map ticket [GDSF：per-function call_cost 如何由用户声明](https://github.com/tanbro/redis_func_cache/issues/16))

## Context

The roadmap's second accepted policy is GDSF (Greedy-Dual-Size, Cherkasova 1998): score = `frequency × cost / size`, theoretically dominant over LRU when miss costs or value sizes are heterogeneous — the norm for function-result caching. The design question was how the user declares `cost`, and what exactly `size` measures.

## Decision

- **Score = `frequency × cost / size`**, kept in the existing ZSET index. On a hit, the frequency is read from a per-entry metadata field (`<hash>:m`, format `"<freq> <cost>"`), incremented, and the score recomputed. On put, the same re-scoring runs in the update branch.
- **`size` is the serialized byte length of the stored value** (`#ARGV[5]`, computed in Lua), with a floor of 1 byte. This is the theoretically correct measure, not an approximation: the score's semantics is "benefit per byte actually held", and the bytes actually held are the serialized value in Redis (mirroring Cao & Irani's file sizes in web caching). No transformation (log, square root) is applied — any monotone distortion of the measure breaks the per-byte rationale. The consequence is **serializer sensitivity**: the same return value has different sizes under different serializers. That is documented as a user-facing caveat (see `docs/usage/considerations.md`), not fixed in code.
- **`cost` is declared as a decorator kwarg** (`@cache.decorate(cost=...)`, default `1.0`), read from the decorator's custom kwargs by `GdsfScripts.calc_ext_args` and passed to the put script as an extension argument (ARGV[7], the same slot MRU uses for its flag — the put ARGV contract is unchanged). The value is coerced with `float()` and validated: non-positive or NaN raises `ValueError`; a non-numeric value propagates whatever `float()` raises. No fallback — a zero cost would collapse every score to zero and reduce eviction to a lexicographic tie. It is deliberately **not** a typed decorator parameter: static typing cannot cover `**kwargs` keys, so discoverability is delegated to documentation.
- **Eviction is a plain `ZPOPMIN`** (as in LFU), not the sampled re-scoring the Hyperbolic policy needs: the GDSF score has no time term, so a stored score is exact as of the entry's last access — ordering by it is deterministic LFU-with-cost semantics, no aging effect to recover.
- **Preset matrix** follows the house pattern: `gdsf_policy` / `gdsf_multiple_policy` / `gdsf_cluster_policy` / `gdsf_cluster_multiple_policy`, argument-less shareable singletons composed over `PICKLE_MD5_HASHER`.
- **Documented limitation of `cost` under per-function keying**: `MultipleKeying` gives each function its own key pair, so within a pair the cost is a constant — and a positive constant cancels in pairwise comparison (`argmin c·f/s == argmin f/s`). `cost` therefore only influences eviction under the single-key-pair variants (`gdsf_policy`, `gdsf_cluster_policy`); under the per-function variants GDSF degrades to `frequency / size` scoring, which remains fully effective. Documented in `docs/usage/considerations.md` and pinned by tests.

## Consequences

- **Positive:** cost- and size-aware eviction with zero structural API changes beyond one decorator kwarg; ARGV contract intact (golden tests extended with the new module); no new Redis command requirements beyond what LFU already uses.
- **Negative:** hit rates are serializer-dependent (user-facing caveat); per-function keying users get no benefit from `cost` (documented); the metadata field doubles the hash fields per entry (same trade-off as Hyperbolic).
- **Neutral:** a wrong `cost` type fails fast at call time (from `calc_ext_args`, i.e. on the first put), not at decoration time.

## References

- Cherkasova, _Improving WWW proxy performance with Greedy-Dual-Size caching_, 1998.
- Cao & Irani, _Cost-Aware WWW Proxy Caching Algorithms_, USENIX 1997.
