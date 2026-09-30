"""Random admission (lru_tr) behavior tests.

The admission rule is probabilistic: a new insertion is rejected with
probability ``p`` while updates always pass. Lua's ``math.random`` cannot be
seeded from the tests, so the aggregate behavior is asserted statistically
(many puts, rejection ratio within a wide interval); the deterministic
aspects — updates pass, boundary probabilities, the ``admission_p``
decorator override, and semantic equivalence with the base LRU-T script —
are asserted exactly.
"""

from __future__ import annotations

import pytest

from redis_func_cache import RedisFuncCache, lru_t_policy, lru_tr_policy
from redis_func_cache.hashing import PICKLE_MD5_HASHER
from redis_func_cache.keying import SingleKeying
from redis_func_cache.policies import Policy
from redis_func_cache.scripts import LruTrScripts

from ._catches import redis_factory

N_PUTS = 100


def _make_cache(name: str, p: float) -> RedisFuncCache:
    policy = Policy(SingleKeying(name), PICKLE_MD5_HASHER, LruTrScripts(p=p))
    return RedisFuncCache(f"{__name__}#{name}", policy, factory=redis_factory, maxsize=N_PUTS)


def _make_echo(cache: RedisFuncCache, **kwds):
    @cache.decorate(**kwds)
    def echo(x):
        return x

    return echo


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
    (index_key, _value_key), _hash_value = cache.policy.locate(cache.prefix, cache.name, echo.__wrapped__, (19,), {})
    admitted = client.zcard(index_key)
    # ~50 expected; a wide interval keeps the test deterministic-ish without
    # being vacuous (a broken p=0 or p=1 script lands far outside).
    assert 30 <= admitted <= 70


def test_update_always_admitted():
    """An entry already in the index is updated regardless of the random draw.

    Uses p = 1.0 (every new insertion rejected): a put for a seeded index
    member must take the update branch, never the rejection branch.
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

        # Seed both keys: the script's consistency cleanup UNLINKs the pair
        # when only one of them exists (which would push the put into the
        # insertion branch); with both present the seeded member takes the
        # update branch (always admitted), never the rejection branch.
        client.zadd(index_key, {member: 0})
        client.hset(value_key, member, b"stale")
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
        assert client.hget(value_key, member) != b"stale"  # value refreshed, not rejected
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
        (index_key, _value_key), _hash_value = cache.policy.locate(
            cache.prefix, cache.name, echo.__wrapped__, (19,), {}
        )
        assert client.zcard(index_key) == 20
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
        (index_key, value_key), _hash_value = cache.policy.locate(cache.prefix, cache.name, echo.__wrapped__, (1,), {})
        assert client.zcard(index_key) == 0
        assert not client.exists(value_key)
    finally:
        cache.purge()


def test_admission_p_kwarg_overrides_baked():
    """The admission_p decorator kwarg overrides the baked probability.

    Baked p = 1.0: the undecorated function is never admitted, while the
    function declaring admission_p = 0.0 is always admitted.
    """
    cache = _make_cache("override", p=1.0)
    cache.purge()
    try:

        @cache.decorate
        def plain(x):
            return x

        exempt = _make_echo(cache, admission_p=0.0)

        for x in range(5):
            plain(x)
            assert exempt(x) == x

        client = redis_factory()
        (plain_key, _vk), _hv = cache.policy.locate(cache.prefix, cache.name, plain.__wrapped__, (4,), {})
        # Single keying: one shared pair — the exempt function's entries are
        # in, the plain function's are not.
        members = set(client.zrange(plain_key, 0, -1))
        assert members
        exempt_hash = cache.policy.calc_hash(exempt.__wrapped__, (4,), {})
        plain_hash = cache.policy.calc_hash(plain.__wrapped__, (4,), {})
        _to_b = lambda v: v.encode() if isinstance(v, str) else v
        assert _to_b(exempt_hash) in members
        assert _to_b(plain_hash) not in members
        assert client.zcard(plain_key) == 5  # exactly the exempt function's 5 entries
    finally:
        cache.purge()


def test_admission_p_invalid_rejected():
    """An invalid admission_p override fails fast, like the GDSF cost kwarg.

    Non-numeric values propagate float()'s error; out-of-range values raise
    ValueError at call time — no fallback.
    """
    with pytest.raises(TypeError):  # float(object()) is a TypeError
        LruTrScripts().calc_ext_args(options={"admission_p": object()})
    with pytest.raises(ValueError):  # float("abc") is a ValueError
        LruTrScripts().calc_ext_args(options={"admission_p": "abc"})
    for bad in (2.0, -1.0, float("nan")):
        with pytest.raises(ValueError):
            LruTrScripts().calc_ext_args(options={"admission_p": bad})

    cache = _make_cache("fallback", p=1.0)
    cache.purge()
    try:
        echo = _make_echo(cache, admission_p=2.0)
        with pytest.raises(ValueError):  # surfaces on the first put, end to end
            echo(1)
    finally:
        cache.purge()


def test_p_validation():
    """Non-numeric p propagates float()'s error; out-of-range or NaN raises ValueError."""
    with pytest.raises(TypeError):  # float(object()) is a TypeError
        LruTrScripts(p=object())
    with pytest.raises(ValueError):  # float("abc") is a ValueError
        LruTrScripts(p="abc")
    with pytest.raises(ValueError):
        LruTrScripts(p=-0.1)
    with pytest.raises(ValueError):
        LruTrScripts(p=1.5)
    with pytest.raises(ValueError):
        LruTrScripts(p=float("nan"))
    assert LruTrScripts(p=0).p == 0.0
    assert LruTrScripts(p="0.25").p == pytest.approx(0.25)
    assert LruTrScripts().p == pytest.approx(LruTrScripts.DEFAULT_P)


def test_calc_ext_args_bakes_p():
    """The effective probability travels as the extension argument (ARGV[7])."""
    assert LruTrScripts().calc_ext_args() == (0.5,)
    assert LruTrScripts(p=0.25).calc_ext_args() == (0.25,)
    # the decorator kwarg overrides the baked value, resolved in calc_ext_args
    assert LruTrScripts(p=1.0).calc_ext_args(options={"admission_p": 0.0}) == (0.0,)
    assert LruTrScripts(p=1.0).calc_ext_args(options={}) == (1.0,)
    assert LruTrScripts(p=1.0).calc_ext_args(options=None) == (1.0,)


def test_semantics_match_lru_t_when_admitting():
    """Semantic drift guard: with p = 0 the script must behave like lru_t_put.

    The same scenario (inserts until eviction, an update, mixed sizes) run
    against lru_t_policy and an admitting lru_tr cache must produce identical
    index ordering and values — the only allowed difference is admission.
    """
    outcomes = {}
    for label, policy in (
        ("t", lru_t_policy),
        ("tr", Policy(SingleKeying("tr"), PICKLE_MD5_HASHER, LruTrScripts(p=0.0))),
    ):
        cache = RedisFuncCache(f"{__name__}#drift-{label}", policy, factory=redis_factory, maxsize=3)
        cache.purge()
        try:

            @cache.decorate
            def echo(x):
                return "v" * x

            for x in range(1, 5):
                echo(x)
            echo(2)  # update of an existing entry

            client = redis_factory()
            (index_key, value_key), _hv = cache.policy.locate(cache.prefix, cache.name, echo.__wrapped__, (1,), {})
            members = client.zrange(index_key, 0, -1)
            outcomes[label] = (members, {m: client.hget(value_key, m) for m in members})
        finally:
            cache.purge()

    assert outcomes["t"] == outcomes["tr"]
    # maxsize = 3, inserts 1..4, then an update: the smallest value went first
    members, values = outcomes["t"]
    assert len(members) == 3
    assert all(values[m] is not None for m in members)
