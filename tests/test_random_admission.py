"""Random admission (lru_tr) behavior tests.

The admission rule is probabilistic: a new insertion is rejected with
probability ``p`` while updates always pass. Lua's ``math.random`` cannot be
seeded from the tests, so the aggregate behavior is asserted statistically
(many puts, rejection ratio within a wide interval); the deterministic
aspects — updates pass, p boundary values, composition plumbing — are
asserted exactly.
"""

from __future__ import annotations

import pytest

from redis_func_cache import RedisFuncCache, lru_tr_policy
from redis_func_cache.hashing import PICKLE_MD5_HASHER
from redis_func_cache.keying import SingleKeying
from redis_func_cache.policies import Policy
from redis_func_cache.scripts import LruTScripts, MruScripts, RandomAdmissionScripts, RrScripts

from ._catches import redis_factory

N_PUTS = 100


def _make_cache(name: str, p: float) -> RedisFuncCache:
    policy = Policy(SingleKeying(name), PICKLE_MD5_HASHER, RandomAdmissionScripts(LruTScripts(), p=p))
    return RedisFuncCache(f"{__name__}#{name}", policy, factory=redis_factory, maxsize=N_PUTS)


def _make_echo(cache: RedisFuncCache, **kwds):
    @cache.decorate(**kwds)
    def echo(x):
        return x

    return echo


def _locate(cache: RedisFuncCache, fn, args=(1,)):
    (index_key, _value_key), _hash_value = cache.policy.locate(cache.prefix, cache.name, fn, args, {})
    return index_key


@pytest.fixture()
def cache():
    cache = RedisFuncCache(__name__, lru_tr_policy, factory=redis_factory, maxsize=N_PUTS)
    cache.purge()
    yield cache
    cache.purge()


def test_rejection_ratio_is_statistical(cache):
    """With p = 0.5, roughly half of the new insertions are admitted."""
    echo = _make_echo(cache)
    for x in range(N_PUTS):
        echo(x)
    client = redis_factory()
    index_key = _locate(cache, echo.__wrapped__)
    admitted = client.zcard(index_key)
    # ~50 expected; a wide interval keeps the test deterministic-ish without
    # being vacuous (a broken p=0 or p=1 prologue lands far outside).
    assert 30 <= admitted <= 70


def test_update_always_admitted():
    """An entry already in the index is updated regardless of the random draw.

    Uses p = 1.0 (every new insertion rejected): the seeded pre-existing entry
    must still be refreshed by the put call.
    """
    cache = _make_cache("update", p=1.0)
    cache.purge()
    try:

        @cache.decorate
        def echo(x):
            return x

        fn = echo.__wrapped__
        client = redis_factory()
        index_key, value_key = cache.policy.locate(cache.prefix, cache.name, fn, (1,), {})[0]
        member = cache.policy.calc_hash(fn, (1,), {})
        member = member.encode() if isinstance(member, str) else member

        # Seed the index member: a put for this hash must take the update
        # branch (always admitted), never the rejection branch.
        client.zadd(index_key, {member: 0})
        cache.policy.put(
            client,
            cache.prefix,
            cache.name,
            fn,
            (1,),
            {},
            value="fresh",
            maxsize=N_PUTS,
            update_ttl=True,
            ttl=60,
        )
        assert client.hget(value_key, member) is not None  # value written, not rejected
        assert client.zcard(index_key) == 1  # updated in place, not re-inserted
    finally:
        cache.purge()


def test_p_zero_admits_all():
    """p = 0 admits every new insertion."""
    cache = _make_cache("p0", p=0.0)
    cache.purge()
    try:
        echo = _make_echo(cache)
        for x in range(20):
            assert echo(x) == x
        client = redis_factory()
        assert client.zcard(_locate(cache, echo.__wrapped__, args=(19,))) == 20
    finally:
        cache.purge()


def test_p_one_rejects_all_new():
    """p = 1 rejects every new insertion; the cached call misses every time."""
    cache = _make_cache("p1", p=1.0)
    cache.purge()
    try:
        calls = []

        @cache.decorate
        def echo(x):
            calls.append(x)
            return x

        assert echo(1) == 1
        assert echo(1) == 1  # rejected put => still a miss on the second call
        assert calls == [1, 1]
        client = redis_factory()
        index_key, value_key = cache.policy.locate(cache.prefix, cache.name, echo, (1,), {})[0]
        assert client.zcard(index_key) == 0
        assert not client.exists(value_key)
    finally:
        cache.purge()


def test_p_validation():
    """Non-numeric p propagates float()'s error; out-of-range or NaN raises ValueError."""
    with pytest.raises(TypeError):  # float(object()) is a TypeError
        RandomAdmissionScripts(LruTScripts(), p=object())
    with pytest.raises(ValueError):  # float("abc") is a ValueError
        RandomAdmissionScripts(LruTScripts(), p="abc")
    with pytest.raises(ValueError):
        RandomAdmissionScripts(LruTScripts(), p=-0.1)
    with pytest.raises(ValueError):
        RandomAdmissionScripts(LruTScripts(), p=1.5)
    with pytest.raises(ValueError):
        RandomAdmissionScripts(LruTScripts(), p=float("nan"))
    assert RandomAdmissionScripts(LruTScripts(), p=0).p == 0.0
    assert RandomAdmissionScripts(LruTScripts(), p="0.25").p == pytest.approx(0.25)
    assert RandomAdmissionScripts(LruTScripts()).p == pytest.approx(0.5)


def test_calc_ext_args_delegates():
    """The composable wrapper must preserve the base policy's ARGV contract."""
    scripts = RandomAdmissionScripts(MruScripts())
    assert scripts.calc_ext_args() == ("mru",)
    assert scripts.get_script == MruScripts.get_script
    assert scripts.put_script == MruScripts.put_script


def test_composable_on_rr():
    """The prologue dispatches its existence check to the base index structure."""
    scripts = RandomAdmissionScripts(RrScripts(), p=0.0)
    assert scripts.index_structure == "set"
    prologue = scripts._admission_prologue()
    assert "'SISMEMBER'" in prologue
    assert RandomAdmissionScripts(LruTScripts())._admission_prologue().count("'ZSCORE'") == 1
