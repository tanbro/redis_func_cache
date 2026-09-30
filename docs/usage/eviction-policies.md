# Eviction Policies

Every cache entry lives in a Redis **key pair**: an index structure (a sorted set for most policies, a plain set for RR) whose members are the per-call hash values, plus a hash holding the serialized results. The eviction policy decides **which entry to drop** when the index exceeds `maxsize` — it is one of the three orthogonal components (keying, hasher, scripts/policy) composed into a [`Policy`][], selected by passing a preset instance to [`RedisFuncCache`][].

This page explains each built-in family: how it orders entries, what workload it fits, and where the idea comes from. All policies except the `Hyperbolic`/`Gdsf` metadata-field details share the same get/put machinery; switching a policy never changes your cache API.

## Baseline recency/order policies

### LRU-T — `lru_t_policy` (default)

Timestamp-based pseudo-LRU: the index score is the microsecond timestamp of the last write (Redis server `TIME`, authoritative), and eviction pops the smallest. This is the house default because it captures LRU's essence — keep the most recently used — while every write is a single `ZADD` on the server side; no client-side recency bookkeeping. LRU's standing rests on the working-set theory of program behavior: recent past access predicts near-future access.

- Reference: Denning, _The Working Set Model for Program Behavior_, ACM Computing Surveys 1968 (the theoretical footing of recency-based replacement); Megiddo & Modha, _ARC: Adaptive Replacement Cache_, USENIX FAST 2003 (the standard account of LRU's weaknesses, including scan pollution).

### LRU — `lru_policy`

Recency with exact ordering semantics, same family as LRU-T but at a different point of the performance/accuracy trade-off (more precise, slower). Same references as LRU-T.

### FIFO / FIFO-T — `fifo_policy`, `fifo_t_policy`

Evict by insertion order, ignoring accesses entirely (FIFO-T only distinguishes the initial-insert timestamp from the update timestamp). Simple and cheap, but provably non-optimal and subject to Belady's anomaly — adding cache space can _increase_ the miss rate, which LRU-family policies never do.

- Reference: Belady, Nelson & Shedler, _An Anomaly in Space-Time Characteristics of Certain Programs Running in a Paging Environment_, CACM 1969 (the anomaly), and the same working-set literature for why FIFO tracks recency poorly.

### MRU — `mru_policy`

Evict the _most_ recently used entry. Almost never right for general workloads, but the correct answer for cyclic access patterns — a program that scans its whole working set in a fixed loop keeps reusing everything except what it touched last, so the newest entry is the safest to drop.

- Reference: Megiddo & Modha, _ARC_, USENIX FAST 2003 (analyzes MRU's advantage under cyclic access).

### RR — `rr_policy`

Random replacement: the index is a plain Redis SET and `SPOP` picks the victim. No bookkeeping at all — a competitive baseline for workloads with little reuse structure. Randomized paging is not naive: it has a proven competitive guarantee LRU shares (both are within a factor of O(h) of the offline optimum, h = cache size), and randomization alone is immune to adversarial access orders.

- Reference: Fiat, Karp, Luby, McGeoch, Sleator & Young, _Competitive Paging Algorithms_, Journal of Algorithms 1991 (competitive analysis of randomized replacement).

## Frequency policies

### LFU — `lfu_policy`

Least frequently used: the index score is an access counter (initialized on insert, incremented on hit). Captures long-term popularity, which recency misses — but classical LFU has a famous aging flaw: an entry that was hot long ago but is dead now still holds its high count and squats on a slot. The built-in script pair does not fix aging — [Hyperbolic](#hyperbolic--hyperbolic_policy) is its aging fix; choose LFU when popularity is stable and pollution is not a concern.

- Reference: O'Neil, O'Neil & Weikum, _The LRU-K Page Replacement Algorithm for Database Disk Buffering_, SIGMOD 1993 (introduces and dissects LFU's aging problem; LRU-K is its classical remedy).

## The upgrade policies

These three were added together as the anti-pollution/heterogeneity upgrade of the baseline set.

### Hyperbolic — `hyperbolic_policy`

LFU with aging: one score `log(freq + 1) / (age + 1) ^ 0.25` merges frequency and recency — a newly inserted entry scores high and decays if not re-accessed, so yesterday's hot entry loses its squat. Age counts from the **last access**: every hit or write resets the entry's clock, so a steadily hot entry's priority stays near `log(freq + 1)` and only an untouched one decays. Requires Redis ≥ 6.2 (`ZRANDMEMBER` for sampled re-scoring; a stored frequency-only score cannot express aging, so the put script re-scores a random sample before evicting). A companion metadata field (`<hash>:m`) holds the frequency and the last-access time.

- Reference: Berger, Sitaraman & Abad, _Hyperbolic Caching: Flexible Caching for Web-Scale Workloads_, USENIX ATC 2020. ([paper](https://www.usenix.org/conference/atc20/presentation/berger))

### GDSF — `gdsf_policy`

Greedy-Dual-Size: score = `frequency × cost / size` — the retained benefit **per byte**, so big results and cheap-to-recompute functions evict first. Built for heterogeneous workloads where values differ in size or functions differ in recomputation cost; the per-function `cost` is a decorator kwarg. `size` is the serialized byte length, so hit rates are serializer-sensitive (see [considerations](considerations.md#the-gdsf-policies-cost-and-size-semantics)).

- References: Cherkasova, _Improving WWW Proxy Performance with Greedy-Dual-Size Caching_, HP Labs Technical Report HPL-98-69, 1998; Cao & Irani, _Cost-Aware WWW Proxy Caching Algorithms_, USENIX Symposium on Internet Technologies and Systems 1997.

### LRU-T with random admission — `lru_tr_policy`

LRU-T plus a probabilistic admission filter: a **new** insertion is rejected with probability `p` (0.5 in the presets, overridable per function with the `reject_p` kwarg), while updates always pass. Rationale: one-pass scans — the classic LRU killer — can only displace an expected `p·S` pre-existing entries, however long the scan. Hit rates are nondeterministic by design, and the policy requires Redis ≥ 7.0 (per-execution `math.random` seeding). Positioned as the **cheap baseline** of scan-resistant admission: it does not approximate TinyLFU's hit rates — that needs a frequency-estimating admission filter (a Count-Min Sketch or similar), deliberately deferred. See the caveats in [considerations](considerations.md#the-random-admission-policies-lru_tr-probabilistic-contract).

- References: Einziger, Friedman & Manes, _TinyLFU: A Fresh Look at Power-Law Key Distribution and the I/O Cost of Flash_, ACM TOCS 2017 (the admission-over-eviction principle); Jaleel, Theobald, Steely & Emer, _High Performance Cache Replacement Using Re-Reference Interval Prediction (RRIP)_, ISCA 2010 (randomized/low-priority insertion as an established scan-resistant baseline).

## Per-function policy kwargs

Two policies take extra per-function arguments through the decorator (alongside the common `serializer` / `excludes` / `ttl` / `update_ttl` / `write_only` options). Both are safe to pass under any policy — a policy whose scripts do not read them simply ignores them — but they only have an effect on the policies below. (A kwarg outside the known option set is a different story: it is forwarded to the Lua script and fails at runtime.)

### `cost` — the GDSF policies

The miss cost of the decorated function, a positive number (coerced with `float()`; unit-free — pick one consistent unit, e.g. milliseconds or a downstream API's charge per call). Defaults to `1.0` when absent; ignored by non-GDSF policies.

```python
from redis_func_cache import gdsf_policy, RedisFuncCache

cache = RedisFuncCache(__name__, gdsf_policy, factory=factory)

@cache(cost=500.0)  # a miss here is ~500 units — retain it over cheap calls
def expensive_api(user_id: int) -> dict: ...

@cache  # no cost kwarg: defaults to 1.0
def cheap_api(key: str) -> str: ...
```

`cost` only changes eviction when functions **share a key pair** — under `gdsf_policy` / `gdsf_cluster_policy` it weighs the cross-function trade-off; under the `gdsf_multiple_*` variants every entry of a pair carries the same cost, so it cannot change their relative order. Full semantics (including why `size` makes hit rates serializer-sensitive): [considerations](considerations.md#the-gdsf-policies-cost-and-size-semantics).

### `reject_p` — the `lru_tr` policies

The probability of rejecting a **new** insertion, within `[0, 1]`. It can be set at two levels: baked into the policy (compose `LruTrScripts(reject_p=...)` — the usual way, applies to every function of the cache), or per function with the decorator kwarg (overrides the baked value). The presets bake `0.5`. A value outside `[0, 1]` (or NaN) raises `ValueError`.

```python
from redis_func_cache import RedisFuncCache
from redis_func_cache.hashing import PickleMd5Hasher
from redis_func_cache.keying import MultipleKeying
from redis_func_cache.policies import Policy
from redis_func_cache.scripts import LruTrScripts

# Policy level (the common case): compose the preset's parts with your own p —
# every decorated function of the cache then admits newcomers with p = 0.2
my_lru_tr = Policy(MultipleKeying("lru_tr-m"), PickleMd5Hasher(), LruTrScripts(reject_p=0.2))
cache = RedisFuncCache(__name__, my_lru_tr, factory=factory)

@cache   # p = 0.2 from the policy
def scanned_table(key: str) -> bytes: ...

@cache(reject_p=0.75)   # per-function override: exempt this one from admission
def hot_key(user_id: int) -> dict: ...
```

Note the trade-off under the single-key-pair variants (`lru_tr_policy` / `lru_tr_cluster_policy`): a lower `p` grabs more slots for that function, skewing the cross-function competition — treat it as a blunt priority knob. See the [probabilistic contract](considerations.md#the-random-admission-policies-lru_tr-probabilistic-contract) for what nondeterminism means for your tests.

## Choosing one

| Workload signal                                  | Start with                   | Redis floor |
| ------------------------------------------------ | ---------------------------- | ----------- |
| General purpose, no special structure            | [`lru_t_policy`][] (default) | 3.2         |
| Big/cheap results vary in size or recompute cost | [`gdsf_policy`][]            | 3.2         |
| Stable popularity, stale hotness is the problem  | [`hyperbolic_policy`][]      | 6.2         |
| One-pass scans keep flushing the cache           | [`lru_tr_policy`][]          | 7.0         |
| Cyclic access over a fixed working set           | [`mru_policy`][]             | 3.2         |
| No reuse structure to exploit                    | [`rr_policy`][]              | 3.2         |

How to read the signals:

- **Start from the default.** `lru_t_policy` is the right answer until measurement says otherwise; recency is a strong default predictor of reuse. Switch only when your hit rate shows a specific, diagnosable failure mode.
- **Scan pollution** (a periodic job or admin query touches every key once and the working set is evicted): `lru_tr` is the cheap fix and costs nothing else — updates always pass, so steady traffic is unaffected. If you also need frequency awareness, `hyperbolic` already resists pollution on its own (a one-hit entry's priority decays immediately), making the two the natural alternatives, not complements.
- **Heterogeneous values or costs**: sizes or recomputation costs differ by more than an order of magnitude — `gdsf`. If your values are near-uniform in size, GDSF's size term cancels and it behaves like LFU with extra bookkeeping.
- **Popularity is stable and old hotness never returns**: plain LFU is fine and cheapest per access; if popularity shifts over days, `hyperbolic` replaces it outright.
- **The floors are per-policy**: field-level TTL (`ttl` on the decorator) separately requires Redis ≥ 7.4 with any policy (see [considerations](considerations.md)).
- **Nothing fits?** Policies compose: `Policy(SingleKeying("my-ns"), PICKLE_MD5_HASHER, MyScripts())` — any custom scorer is a small Lua pair.

[`Policy`]: redis_func_cache.policies.Policy
[`RedisFuncCache`]: redis_func_cache.cache.RedisFuncCache
[`lru_t_policy`]: redis_func_cache.policies.lru.lru_t_policy
[`gdsf_policy`]: redis_func_cache.policies.gdsf.gdsf_policy
[`hyperbolic_policy`]: redis_func_cache.policies.hyperbolic.hyperbolic_policy
[`lru_tr_policy`]: redis_func_cache.policies.lru.lru_tr_policy
[`mru_policy`]: redis_func_cache.policies.mru.mru_policy
[`rr_policy`]: redis_func_cache.policies.rr.rr_policy
