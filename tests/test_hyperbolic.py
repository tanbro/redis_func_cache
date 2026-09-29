"""Hyperbolic (LFU-with-aging) policy behavior tests.

Unlike the other ZSET policies, the hyperbolic score mixes access frequency
with insertion age, so its contract has three hyperbolic-specific aspects:

- the score equals ``log(freq + 1) / (age + 1) ^ 0.25`` after each access,
- a companion metadata field (``<hash>:m``) lives in the value hash,
- an entry whose insertion time is backdated ages out even if its frequency
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
    assert member + b":m" in client.hkeys(value_key)
    freq, insert_ms = client.hget(value_key, member + b":m").split()
    assert int(freq) == 1
    assert int(insert_ms) > 0


def test_score_formula(cache, echo):
    """After n accesses the ZSET score must equal log(n+1)/(age+1)^0.25."""
    for _ in range(4):
        assert echo(1) == 1
    client = redis_factory()
    index_key, value_key, member = _locate(cache, echo)
    [(member_z, score)] = client.zrange(index_key, 0, -1, withscores=True)
    assert member_z == member
    freq, insert_ms = client.hget(value_key, member + b":m").split()
    freq = int(freq)
    assert freq == 4  # 1 on insert + 3 hits
    age = max(time.time() * 1000 - int(insert_ms), 0) / 1000
    # the host clock and the Redis server clock are compared, so allow for skew
    assert score == pytest.approx(math.log(freq + 1) / math.pow(max(age, 0) + 1, 0.25), rel=0.05)


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
    hot_freq = int(client.hget(value_key, member + b":m").split()[0])
    assert hot_freq == 10  # 1 on insert + 9 hits

    # Backdate the hot entry's insertion time by ~10 days; its stored score
    # stays high, but its true recomputed priority must now be the lowest
    backdated_ms = int((time.time() - 10 * 86400) * 1000)
    client.hset(value_key, member + b":m", f"{hot_freq} {backdated_ms}")

    # Insert one more entry: must evict the backdated stale-hot entry even
    # though its frequency is by far the highest
    assert echo(3) == 3
    remaining = set(client.zrange(index_key, 0, -1))
    assert len(remaining) == MAXSIZE
    assert member not in remaining
