"""Hyperbolic (LFU-with-aging) policy behavior tests.

Unlike the other ZSET policies, the hyperbolic score mixes access frequency
with age since the last access, so its contract has three hyperbolic-specific
aspects:

- the score equals ``log(freq + 1) / (age + 1) ^ 0.25`` after each access,
  where age counts from the LAST access (each access resets the clock),
- a companion metadata field (``<hash>:m``) lives in the value hash,
- an entry whose last-access time is backdated ages out even if its frequency
  is the highest — the LFU weakness this policy exists to fix (put eviction
  re-scores a random sample, so it must not trust the stale stored score).
"""

from __future__ import annotations

import math
import time

import pytest

from redis_func_cache import RedisFuncCache, hyperbolic_policy

from ._catches import redis_factory

MAXSIZE = 3


def _make_echo(cache: RedisFuncCache):
    @cache
    def echo(x):
        return x

    return echo


@pytest.fixture()
def cache():
    cache = RedisFuncCache(__name__, hyperbolic_policy, factory=redis_factory, maxsize=MAXSIZE)
    cache.purge()
    yield cache
    cache.purge()


@pytest.fixture()
def echo(cache):
    return _make_echo(cache)


def _locate(cache: RedisFuncCache, echo, args=(1,)):
    """(index_key, value_key, hash_field) of one call — under SingleKeying the pair is shared."""
    (index_key, value_key), hash_value = cache.policy.locate(cache.prefix, cache.name, echo.__wrapped__, args, {})
    return index_key, value_key, hash_value  # type: ignore[return-value]


def test_metadata_field(cache, echo):
    """The value hash holds both the value and the companion '<hash>:m' metadata."""
    echo(1)
    client = redis_factory()
    _index_key, value_key, member = _locate(cache, echo)
    member_bytes = member.encode() if isinstance(member, str) else member
    assert member_bytes + b":m" in client.hkeys(value_key)
    result = client.hget(value_key, member_bytes + b":m")
    assert result is not None
    freq, last_access_ms = result.split()
    assert int(freq) == 1
    assert int(last_access_ms) > 0


def test_score_formula(cache, echo):
    """After n accesses the ZSET score must equal log(n+1)/(age+1)^0.25."""
    for _ in range(4):
        assert echo(1) == 1
    client = redis_factory()
    index_key, value_key, member = _locate(cache, echo)
    [(member_z, score)] = client.zrange(index_key, 0, -1, withscores=True)
    assert member_z == member
    member_bytes = member.encode() if isinstance(member, str) else member
    result = client.hget(value_key, member_bytes + b":m")
    assert result is not None
    freq, last_access_ms = result.split()
    freq = int(freq)
    assert freq == 4  # 1 on insert + 3 hits
    # age counts from the last access (reset on every hit)
    age = max(time.time() * 1000 - int(last_access_ms), 0) / 1000
    # the host clock and the Redis server clock are compared, so allow for skew
    assert score == pytest.approx(math.log(freq + 1) / math.pow(max(age, 0) + 1, 0.25), rel=0.05)


def test_hit_resets_the_clock(cache, echo):
    """A hit rewrites the metadata timestamp: age is measured from the last access.

    Without the reset, a long-lived hot entry's priority would decay to zero
    as its insertion age grows and it would always evict — the degeneration
    the Hyperbolic paper's per-access clock reset exists to prevent.
    """
    assert echo(1) == 1
    client = redis_factory()
    _index_key, value_key, member = _locate(cache, echo)
    member_bytes = member.encode() if isinstance(member, str) else member

    # Backdate the metadata far into the past, as if nothing had been accessed
    backdated_ms = int((time.time() - 10 * 86400) * 1000)
    client.hset(value_key, member_bytes + b":m", f"1 {backdated_ms}")

    assert echo(1) == 1  # a hit — must reset the clock, not keep the backdated age

    result = client.hget(value_key, member_bytes + b":m")
    assert result is not None
    freq, last_access_ms = result.split()
    assert int(freq) == 2
    assert int(last_access_ms) > backdated_ms + 86400 * 1000 // 2  # rewritten to ~now
    index_key = _locate(cache, echo)[0]
    [(member_z, score)] = client.zrange(index_key, 0, -1, withscores=True)
    assert member_z == member
    assert score == pytest.approx(math.log(3), rel=0.05)  # age 0 after the hit


def test_aging_evicts_stale_hot_entry(cache, echo):
    """A backdated high-frequency entry must evict before fresh entries.

    Plain LFU keeps the highest-frequency entry forever. Here put eviction
    recomputes priorities from the metadata, so the backdated entry's aged
    priority drops below the fresh entries' and it is evicted.
    """
    # Pump one entry's frequency well above the others, then fill the cache
    for _ in range(10):
        assert echo(0) == 0
    assert echo(1) == 1
    assert echo(2) == 2

    client = redis_factory()
    index_key, value_key, member = _locate(cache, echo, args=(0,))
    member_bytes = member.encode() if isinstance(member, str) else member
    result = client.hget(value_key, member_bytes + b":m")
    assert result is not None
    hot_freq = int(result.split()[0])
    assert hot_freq == 10  # 1 on insert + 9 hits

    # Backdate the hot entry's last-access time by ~10 days; its stored score
    # stays high, but its true recomputed priority must now be the lowest
    backdated_ms = int((time.time() - 10 * 86400) * 1000)
    client.hset(value_key, member_bytes + b":m", f"{hot_freq} {backdated_ms}")

    # Insert one more entry: must evict the backdated stale-hot entry even
    # though its frequency is by far the highest
    assert echo(3) == 3
    remaining = set(client.zrange(index_key, 0, -1))
    assert len(remaining) == MAXSIZE
    assert member not in remaining
