# Design Note: Purging Cache Structures Without Blocking Redis

## Background

`purge_all_pairs` (and its async mirror `apurge_all_pairs`) deletes every Redis key a policy owns. The two
policy shapes differ structurally:

- **Single policies** own exactly one static key pair (`...:0` ZSET + `...:1`
  HASH). `Keying.purge_all_pairs` calls `DEL` on the two names from `calc_key_pair()` —
  two keys, one command, no enumeration. This variant is already correct and needs no
  change.
- **Multiple policies** own one key pair *per decorated function*, discovered at
  decoration time. There is no static key list, so the purge has to enumerate:

```python
# Pre-v1.0 implementation (policies/base.py, removed)
pat = f"{self.cache.prefix}{self.cache.name}:{self.__key__}:*"
if keys := client.keys(pat):
    return client.delete(*keys)
```

Two properties of this implementation are production hazards:

1. **`KEYS` blocks the server.** `KEYS` is O(N) over the *entire* keyspace and runs to
   completion on Redis's single thread. On a large instance the call stalls every
   other client for the whole scan — the classic Redis anti-pattern, and the same
   reason the vacuum design (see [Vacuuming Expired Per-Field Cache
   Entries](field-ttl-vacuum.md)) moved its enumeration to `SCAN`.
2. **One giant `DELETE`.** Every matched key travels in a single `DEL` command.
   Deleting many keys touches many allocation arenas; a wide purge can hold the server
   busy longer than any caller expects, and the command payload scales with the
   cache's fan-out.

## Goals and non-goals

- **Goals**: non-blocking enumeration (`SCAN`), bounded per-command work (batched
  `UNLINK`), a cache-level entry point so users do not reach into `cache.policy`.
- **Non-goals**: changing what "purge" means (it remains *delete all structures,
  return the number of keys deleted*); touching the get/put/get-size paths; automatic
  or scheduled purging — that stays the caller's decision.

## Options considered

| Option | Verdict | Why |
| --- | --- | --- |
| `SCAN` + batched `UNLINK` | **Adopted** | Non-blocking enumeration, bounded command size, asynchronous memory reclaim. See below. |
| Keep `KEYS`, keep single `DEL` | Rejected | The status quo: O(N) server-wide stall and an unbounded single command. |
| One Lua script enumerating and deleting | Rejected | A script may only touch keys sharing one cluster slot, while multiple policies spread pairs across slots — impossible in cluster mode; and a whole-scan script blocks the single-threaded server for its duration (same reasoning as the *whole vacuum* rejection in [the vacuum note](field-ttl-vacuum.md)). |
| `FLUSHDB` / `FLUSHALL` | Rejected | Flushes the *entire database*, including keys the library does not own. A purge must be scoped to the cache's own prefix. |
| Swap-in generation keys (rename prefix, delete old lazily) | Rejected | Changes the key layout and every script for a maintenance operation; the vacuum note already rejected generation keys for the same reason. |
| Keyspace notifications / background sweeper | Rejected | Purge is an explicit administrative action; nothing here benefits from push-based triggers. |

## Chosen design

### Batched `UNLINK` over `SCAN`

The replacement loop, identical in shape for sync and async:

1. `SCAN MATCH <prefix><name>:<__key__>:*` (via `client.scan_iter`, which pages with a
   default `COUNT` hint and never blocks);
2. buffer matched keys and call **`UNLINK`** in batches of `batch_size` (default 500,
   matching `vacuum`);
3. accumulate and return the total number of keys unlinked.

`UNLINK` over `DEL`: the key removal from the keyspace is O(1) on the caller's path
while the memory reclamation happens incrementally in a background thread
(Redis ≥ 4.0). The return value semantics are identical. Small caches (a handful of
keys) gain nothing from `UNLINK` over `DEL`, but the code stays uniform and the batch
bound keeps worst cases flat.

The pattern is deliberately `...:{__key__}:*` — *not* the `:*:0` pattern of
`iterate_key_pairs`: a purge must take the hash (`:1`) along with the sorted set (`:0`),
so the enumeration cannot reuse the vacuum's pair iterator even though both start from
`SCAN`.

### Enumeration

Single policies keep deleting their static pair — nothing to enumerate. Multiple
policies enumerate with `scan_iter` inline in `purge`/`apurge` (the `:*` pattern and
the flat key list differ from `iterate_key_pairs`'s `:*:0`-pattern pair list, so sharing
would complicate both call sites for no reuse).

### Cache-level delegation

`RedisFuncCache` gains `purge()` / `apurge()` as one-line delegations to the
policy — the same shape as the `vacuum()` / `avacuum()` delegations — so the public
workflow is symmetric:

```python
from redis import Redis
from redis_func_cache import lru_multiple_policy, RedisFuncCache

pool = Redis.ConnectionPool.from_url("redis://")
cache = RedisFuncCache("my-cache", lru_multiple_policy, factory=lambda: Redis.from_pool(pool))


@cache
def func_a(x):
    ...


@cache
def func_b(x):
    ...


cache.purge()  # drop every structure this cache owns (each function's ZSET + HASH)
# or, in async code:
# await cache.apurge()
```

- `cache.purge(batch_size=500)` deletes every key the cache owns and returns the
  number deleted. `cache.apurge()` is the async mirror; the policy-level
  `cache.policy.purge_all_pairs(redis_client, prefix, name)` remains available — the policy-level signature takes the client and the key namespace explicitly, while the cache-level `cache.purge()` supplies both for you.
- The `batch_size` parameter is new and keyword-friendly; the return value keeps its
  meaning (number of keys removed), so existing callers are unaffected.
- The optional `redis_client` argument is checked statically: it must have the same
  sync/async kind as the cache's own client (enforced by the type checker via the
  class's client type variable); no runtime type guard is performed.

### Naming: the maintenance vocabulary

The policy-level maintenance methods form a granularity matrix, and the names state
their unit of work explicitly:

| Method | Unit of work |
| --- | --- |
| `purge_all_pairs` / `apurge_all_pairs` | enumerate and delete *every* key pair of the namespace |
| `purge_one_pair` / `apurge_one_pair` | delete *one* (index, value) key pair outright |
| `vacuum_all_pairs` / `avacuum_all_pairs` | sweep expired members of *every* key pair |
| `vacuum_one_pair` / `avacuum_one_pair` | sweep expired members of *one* key pair |
| `iterate_key_pairs` / `aiterate_key_pairs` | enumerate the key pairs (read-only) |

The suffix is load-bearing at the policy layer because both granularities exist there,
and `purge_one_pair` takes raw key names (from `iterate_key_pairs` / `calc_key_pair`)
so its semantics are unambiguous under every keying variant.

The cache-level facades keep the short names `purge` / `apurge` / `vacuum` / `avacuum`:
the cache has exactly one granularity — *the whole cache it names* — so the suffix has
nothing to contrast with, and cache users are not asked to think in key pairs. The rule
is: **suffixes appear only on the layer where the granularity contrast exists**.

A cache-level *function*-scoped purge (e.g. `purge_one_pair(fn, ...)` keyed by the
decorated function) was considered and rejected: under `MultipleKeying` one function's
entries span several key pairs, so a pair computed from `(fn, args)` is one shard —
the name would promise "this function's cache" while deleting only a fragment. If
function-level invalidation is wanted later, it should enumerate all of a function's
pairs and is a separate feature, not an overload of pair-level purge.

### Namespace purge

A natural follow-up question is "drop *everything* belonging to this cache, across all
its policies" (e.g. after renaming a function or retiring a decorator). That is a
prefix-level `SCAN` + batched `UNLINK` over `f"{prefix}*"` and does not belong to any
single policy. It is recorded as a **separate, optional API** (`purge_namespace()`),
to be added only if a use case materializes — the per-policy purge plus Redis's own
structure TTL already covers the common cases. Listing it here keeps the decision from
being re-litigated.
