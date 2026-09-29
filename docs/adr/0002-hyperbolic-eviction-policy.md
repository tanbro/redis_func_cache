# ADR 0002: Hyperbolic (LFU-with-aging) Eviction Policy

- **Status:** Accepted
- **Date:** 2026-09-29
- **Implements:** ADR 0001 (Accepted #1)
- **Deciders:** maintainers

## Context

ADR 0001 accepted Hyperbolic Caching (Berger et al., USENIX ATC 2020) as the
cheapest real win beyond LRU/LFU: one ZSET score capturing recency *and*
frequency, `score = log(freq + 1) / age^d` (d = 0.25), fixing LFU's classical
weakness — stale hot entries never age out — without a decay task.

Policies are stateless: all state must live in Redis, and the key-pair layout
(index ZSET `:0` + value HASH `:1`) is pinned by the golden tests.

## Decision

- **Score** `priority = log(freq + 1) / (age_seconds + 1) ^ 0.25`, where age
  counts from the entry's *insertion time* and time is the **Redis server
  TIME** (never client clocks). The `+1` on the age term keeps fresh entries
  finite and bounds the effect of microsecond-level age jitter.
- **Per-entry metadata** lives in a companion field `'<hash>:m'` of the value
  HASH, holding `"<freq> <insert_time_us>"`. Value fields are 32-byte digests,
  metadata fields 34 bytes — the namespaces cannot collide, the key-pair
  layout is unchanged, and `get_size` (ZCARD) still counts one member per
  entry. HEXPIRE (per-field TTL) applies to both fields together. Corrupt or
  missing metadata restarts the entry (freq = 1, insert = now).
- **Clock-reset guard**: age is floored at 0; a backwards server-clock step
  must not produce a negative base for the fractional power (NaN scores would
  corrupt the index ordering).
- **Eviction by sampling, not by stored score.** Scores are recomputed only
  on access, so between accesses a stored score can only *over-estimate* the
  true priority (age grows monotonically). A plain `ZPOPMIN` would therefore
  keep a recently-pumped entry forever — precisely the LFU weakness this
  policy exists to fix. Instead each eviction samples 8 random members
  (`ZRANDMEMBER`, hence Redis ≥ 6.2), recomputes their true priorities from
  the metadata, and evicts the sampled minimum — the same shape as Redis's
  own sampled `maxmemory` eviction. Ghosts (index member whose value field is
  gone) are evicted first. Cost per eviction event: O(SAMPLE) hash lookups;
  per-access cost stays O(log N).
- Presets: `hyperbolic_policy` / `hyperbolic_multiple_policy` /
  `hyperbolic_cluster_policy` / `hyperbolic_cluster_multiple_policy`
  (naming and keying matrix per ADR 0001). No `calc_ext_args`; the put ARGV
  contract is untouched.

## Consequences

- **Positive**: frequency *and* aging in one ZSET score; stale hot entries
  evict before fresh ones (pinned by `tests/test_hyperbolic.py`); no decay
  task; layout unchanged.
- **Negative / accepted coarseness**:
  - Sampling makes eviction probabilistic — like Redis's own LFU, the victim
    is the sampled minimum, not the global minimum.
  - An entry's stored score is only refreshed when it is accessed or sampled
    at eviction time; entries that are neither accessed nor evicted against
    keep a stale (optimistic) score. Sampling bounds the damage.
  - Score is sensitive to the serializer only through entry count, not value
    size (unlike GDSF).
  - The metadata field doubles the value HASH's HLEN. `get_size` and vacuum
    are unaffected (they count/probe index members and value fields).
- **Watch-out**: `ZRANDMEMBER` requires Redis ≥ 6.2 (older than the generic
  floor behavior of the other policies' scripts, which only need Redis ≥ 3.2
  era commands plus optional 7.4 HEXPIRE).

## References

- Berger et al., *Hyperbolic Caching*, USENIX ATC 2020.
- ADR 0001: Eviction Policy Roadmap Beyond LRU/LRU-T/LFU.
