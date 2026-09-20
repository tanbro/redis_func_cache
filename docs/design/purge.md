---
status: draft
description: |
   Targeted at the next minor release.
   This note records how `purge` is implemented today, why its multiple-policy
   variant is unsuitable for production Redis, the alternatives considered,
   and the design of the replacement: SCAN-based enumeration with batched
   UNLINK, a cache-level delegation, and an optional namespace purge.
---

# Design Note: Purging Cache Structures Without Blocking Redis

## Background

{meth}`~redis_func_cache.policies.abstract.AbstractPolicy.purge` (and its async
mirror {meth}`~redis_func_cache.policies.abstract.AbstractPolicy.apurge`) deletes
every Redis key a policy owns. The two policy shapes differ structurally:

- **Single policies** own exactly one static key pair (`...:0` ZSET + `...:1`
  HASH). `BaseSinglePolicy.purge` calls `DEL` on the two names from
  `calc_keys()` — two keys, one command, no enumeration. This variant is already
  correct and needs no change.
- **Multiple policies** own one key pair *per decorated function*, discovered at
  decoration time. There is no static key list, so the purge has to enumerate:

```python
# src/redis_func_cache/policies/base.py — BaseMultiplePolicy.purge (current)
pat = f"{self.cache.prefix}{self.cache.name}:{self.__key__}:*"
if keys := client.keys(pat):
    return client.delete(*keys)
```

Two properties of this implementation are production hazards:

1. **`KEYS` blocks the server.** `KEYS` is O(N) over the *entire* keyspace and
   runs to completion on Redis's single thread. On a large instance the call
   stalls every other client for the whole scan — the classic Redis
   anti-pattern, and the same reason the vacuum design (see
   {doc}`field-ttl-vacuum`) moved its enumeration to `SCAN`.
2. **One giant `DELETE`.** Every matched key travels in a single `DEL` command.
   Deleting many keys touches many allocation arenas; a wide purge can hold the
   server busy longer than any caller expects, and the command payload scales
   with the cache's fan-out.

## Goals and non-goals

- **Goals**: non-blocking enumeration (`SCAN`), bounded per-command work
  (batched `UNLINK`), a cache-level entry point so users do not reach into
  `cache.policy`, and an optional namespace-level purge.
- **Non-goals**: changing what "purge" means (it remains *delete all structures,
  return the number of keys deleted*); touching the get/put/get-size paths;
  automatic or scheduled purging — that stays the caller's decision.

## Options considered

| Option | Verdict | Why |
| --- | --- | --- |
| `SCAN` + batched `UNLINK` | **Adopted** | Non-blocking enumeration, bounded command size, asynchronous memory reclaim. See below. |
| Keep `KEYS`, keep single `DEL` | Rejected | The status quo: O(N) server-wide stall and an unbounded single command. |
| One Lua script enumerating and deleting | Rejected | A script may only touch keys sharing one cluster slot, while multiple policies spread pairs across slots — impossible in cluster mode; and a whole-scan script blocks the single-threaded server for its duration (same reasoning as the *whole vacuum* rejection in {doc}`field-ttl-vacuum`). |
| `FLUSHDB` / `FLUSHALL` | Rejected | Flushes the *entire database*, including keys the library does not own. A purge must be scoped to the cache's own prefix. |
| Swap-in generation keys (rename prefix, delete old lazily) | Rejected | Changes the key layout and every script for a maintenance operation; the vacuum note already rejected generation keys for the same reason. |
| Keyspace notifications / background sweeper | Rejected | Purge is an explicit administrative action; nothing here benefits from push-based triggers. |

## Chosen design

### Batched `UNLINK` over `SCAN`

The replacement loop, identical in shape for sync and async:

1. `SCAN MATCH <prefix><name>:<__key__>:*` (via `client.scan_iter`, which pages
   with a default `COUNT` hint and never blocks);
2. buffer matched keys and call **`UNLINK`** in batches of `batch_size`
   (default 500, matching `vacuum`);
3. accumulate and return the total number of keys unlinked.

`UNLINK` over `DEL`: the key removal from the keyspace is O(1) on the
caller's path while the memory reclamation happens incrementally in a
background thread (Redis ≥ 4.0). The return value semantics are identical.
Small caches (a handful of keys) gain nothing from `UNLINK` over `DEL`, but
the code stays uniform and the batch bound keeps worst cases flat.

The pattern is deliberately `...:{__key__}:*` — *not* the `:*:0` pattern of
`calc_key_pairs`: a purge must take the hash (`:1`) along with the sorted set
(`:0`), so the enumeration cannot reuse the vacuum's pair iterator even
though both start from `SCAN`.

### Enumeration: reuse `calc_key_pairs` where it fits

Single policies keep deleting their static pair — nothing to enumerate.
Multiple policies enumerate with `scan_iter` inline in `purge`/`apurge`
(the `:*` pattern and the flat key list differ from `calc_key_pairs`'s
`:*:0`-pattern pair list, so sharing would complicate both call sites for
no reuse).

### Cache-level delegation

`RedisFuncCache` gains `purge()` / `apurge()` as one-line delegations to the
bound policy — the same shape as the existing `vacuum()` / `avacuum()`
delegations — so the public workflow is symmetric:

```python
cache.purge()        # drop every structure this cache owns
cache.avacuum()      # or: clean ghosts without dropping live entries
```

### Namespace purge

A natural follow-up question is "drop *everything* belonging to this cache,
across all its policies" (e.g. after renaming a function or retiring a
decorator). That is a prefix-level `SCAN` + batched `UNLINK` over
`f"{prefix}*"` and does not belong to any single policy. It is recorded as a
**separate, optional API** on `RedisFuncCache` (`purge_namespace()`), to be
added only if a use case materializes — the per-policy purge plus Redis's own
structure TTL already covers the common cases. Listing it here keeps the
decision from being re-litigated.

### API sketch

```python
class AbstractPolicy:
    def purge(self, batch_size: int = 500) -> int:
        """Delete every Redis key this policy owns.

        Returns the number of keys deleted.
        """

    async def apurge(self, batch_size: int = 500) -> int: ...


class RedisFuncCache:
    def purge(self) -> int: ...      # delegate to policy
    async def apurge() -> int: ...
```

- The sync/async client guards and `RuntimeError` messages stay as they are.
- Adding the `batch_size` parameter to `purge`/`apurge` is
  backward-compatible (new keyword-only argument with a default); the return
  value keeps its meaning (number of keys removed).
- `BaseSinglePolicy.purge` keeps its direct two-key `DEL` (no batching
  needed); only `BaseMultiplePolicy` changes implementation.

## Test plan

Integration tests against real Redis, sync and async mirrors:

1. **Single policy purge.** Decorate one function, fill, purge → both keys
   gone, return value `2`, subsequent call recomputes.
2. **Multiple policy purge.** Decorate two functions, fill both, purge →
   all four keys gone (enumeration across pairs), return value `4`.
3. **Batching.** Fill enough key pairs that `batch_size=1` forces multiple
   unlink rounds; purge still removes everything and the count is exact.
4. **Empty cache.** Purge on a never-used cache returns `0`.
5. **Cache-level delegation.** `cache.purge()` equals the policy's result and
   clears the same keys.
6. **Client-nature guard.** `purge()` on an async-client cache raises
   `RuntimeError` (unchanged behavior).

## Rollout

1. Rework `BaseMultiplePolicy.purge` / `apurge` to `SCAN` + batched `UNLINK`;
   leave `BaseSinglePolicy` untouched.
2. Add `RedisFuncCache.purge` / `apurge` delegations.
3. CHANGELOG entry noting the multiple-policy purge no longer uses `KEYS`
   (behavior-preserving except for blocking characteristics) and
   `.. versionadded::` markers — version to be decided at release.
