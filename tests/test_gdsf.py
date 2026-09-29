"""GDSF (Greedy-Dual-Size) policy behavior tests.

The GDSF score is ``freq * cost / size`` — the retained benefit per byte.
Its contract has three GDSF-specific aspects:

- the score equals ``freq * cost / size`` after each access, with ``size``
  the serialized byte length of the stored value,
- a companion metadata field (``<hash>:m``) holds ``"<freq> <cost>"``,
- the ``cost`` decorator kwarg (default 1.0) differentiates functions only
  under the single-key-pair keying: entries of one function share a key pair,
  so a per-function cost is an in-pair constant that cannot change the
  relative order — but a different serializer does, through the value size.
"""

from __future__ import annotations

import pytest

from redis_func_cache import RedisFuncCache, gdsf_policy
from redis_func_cache.policies.gdsf import gdsf_multiple_policy
from redis_func_cache.scripts import GdsfScripts

from ._catches import redis_factory

MAXSIZE = 3


def _make_echo(cache: RedisFuncCache, **kwds):
    @cache.decorate(**kwds)
    def echo(x):
        return x

    return echo


@pytest.fixture()
def cache():
    cache = RedisFuncCache(__name__, gdsf_policy, factory=redis_factory, maxsize=MAXSIZE)
    cache.purge()
    yield cache
    cache.purge()


@pytest.fixture()
def echo(cache):
    return _make_echo(cache)


def _locate(cache: RedisFuncCache, fn, args=(1,)):
    """(index_key, value_key, hash_field) of one call — under SingleKeying the pair is shared."""
    (index_key, value_key), hash_value = cache.policy.locate(cache.prefix, cache.name, fn, args, {})
    return index_key, value_key, hash_value  # type: ignore[return-value]


def _b(member):
    """The hash field as bytes (locate may return it as str or bytes)."""
    return member.encode() if isinstance(member, str) else member


def test_metadata_field(cache, echo):
    """The value hash holds the value and the '<hash>:m' = '<freq> <cost>' metadata."""
    echo(1)
    client = redis_factory()
    _index_key, value_key, member = _locate(cache, echo.__wrapped__)
    member_bytes = member.encode() if isinstance(member, str) else member
    result = client.hget(value_key, member_bytes + b":m")
    assert result is not None
    freq, cost = result.split()
    assert int(freq) == 1
    assert float(cost) == pytest.approx(1.0)  # default cost


def test_score_formula(cache, echo):
    """After n accesses the ZSET score must equal n * cost / size."""
    for _ in range(4):
        assert echo(1) == 1
    client = redis_factory()
    index_key, value_key, member = _locate(cache, echo.__wrapped__)
    [(member_z, score)] = client.zrange(index_key, 0, -1, withscores=True)
    assert member_z == member
    member_bytes = member.encode() if isinstance(member, str) else member
    value = client.hget(value_key, member_bytes)
    assert value is not None
    size = len(value)
    freq = 4  # 1 on insert + 3 hits
    assert score == pytest.approx(freq * GdsfScripts.DEFAULT_COST / size)


def test_cost_kwarg_reaches_score(cache):
    """A declared cost scales the score of the declaring function."""
    echo = _make_echo(cache, cost=2.5)
    echo(1)
    client = redis_factory()
    index_key, value_key, member = _locate(cache, echo.__wrapped__)
    [(member_z, score)] = client.zrange(index_key, 0, -1, withscores=True)
    assert member_z == member
    member_bytes = member.encode() if isinstance(member, str) else member
    value = client.hget(value_key, member_bytes)
    assert value is not None
    size = len(value)
    assert score == pytest.approx(2.5 / size)
    result = client.hget(value_key, member_bytes + b":m")
    assert result is not None
    _freq, cost = result.split()
    assert float(cost) == pytest.approx(2.5)


def test_cost_validated():
    """Non-numeric cost propagates float()'s error; non-positive or NaN raises ValueError."""
    scripts = GdsfScripts()
    with pytest.raises(TypeError):  # float(object()) is a TypeError
        scripts.calc_ext_args(options={"cost": object()})
    with pytest.raises(ValueError):  # float("abc") is a ValueError
        scripts.calc_ext_args(options={"cost": "abc"})
    with pytest.raises(ValueError):
        scripts.calc_ext_args(options={"cost": 0})
    with pytest.raises(ValueError):
        scripts.calc_ext_args(options={"cost": -1.0})
    with pytest.raises(ValueError):
        scripts.calc_ext_args(options={"cost": float("nan")})
    assert scripts.calc_ext_args(options={}) == (1.0,)
    assert scripts.calc_ext_args(options=None) == (1.0,)
    assert scripts.calc_ext_args(options={"cost": "2"}) == (2.0,)


def test_cost_orders_functions_in_single_pair(cache):
    """Under single keying, a lower-cost function's entry is evicted first.

    Two functions share one key pair (SingleKeying); with equal value sizes
    and frequency, the one declaring the smaller cost per byte has the lower
    benefit density and must go first.
    """

    @cache.decorate(cost=1.0)
    def cheap(x):
        return x

    @cache.decorate(cost=100.0)
    def dear(x):
        return x

    # distinct qualnames → distinct fingerprints → two entries in the shared pair
    cheap(1)
    dear(1)

    client = redis_factory()
    index_key, value_key, cheap_member = _locate(cache, cheap.__wrapped__)
    _index_key, _value_key, dear_member = _locate(cache, dear.__wrapped__)
    cheap_value = client.hget(value_key, _b(cheap_member))
    dear_value = client.hget(value_key, _b(dear_member))
    assert cheap_value is not None and dear_value is not None
    assert len(cheap_value) == len(dear_value)  # same value, same size

    # Fill the cache; with equal sizes and frequencies, cost alone decides
    for i in range(2, MAXSIZE + 2):
        cheap(i)
        dear(i)
    remaining = set(client.zrange(index_key, 0, -1))
    assert cheap_member not in remaining  # cost 1.0/size < 100.0/size
    assert dear_member in remaining
    assert len(remaining) == MAXSIZE


def test_size_prefers_small_values(cache):
    """Between equal-frequency entries of one function, the larger value scores lower."""

    @cache
    def echo(x):
        return "x" * (10 * x)  # bigger argument, bigger serialized value

    for x in (1, 5):
        assert echo(x) == "x" * (10 * x)
    client = redis_factory()
    index_key, value_key, m1 = _locate(cache, echo.__wrapped__, args=(1,))
    _index_key, _value_key, m5 = _locate(cache, echo.__wrapped__, args=(5,))
    v1 = client.hget(value_key, _b(m1))
    v5 = client.hget(value_key, _b(m5))
    assert v1 is not None and v5 is not None
    assert len(v5) > len(v1)  # distinct sizes for the same function

    scores = dict(client.zrange(index_key, 0, -1, withscores=True))
    assert scores[m1] > scores[m5]  # same freq and cost: the larger value scores lower


def test_multiple_keying_cost_is_in_pair_constant():
    """Documented contract: under per-function keying the cost cannot reorder a pair.

    Every entry of one function shares the cost, so scores are proportional to
    frequency/size regardless of the declared cost. Pin that two caches of the
    same function with different costs evict in the same order.
    """

    def run(cost):
        cache = RedisFuncCache(f"{__name__}#{cost}", gdsf_multiple_policy, factory=redis_factory, maxsize=2)
        cache.purge()

        @cache.decorate(cost=cost)
        def echo(x):
            return "x" * (10 * x)

        try:
            echo(1)
            echo(5)
            echo(9)  # evicts the larger x=5 value (same freq, bigger size)
            client = redis_factory()
            (index_key, _value_key), _hash_value = cache.policy.locate(
                cache.prefix, cache.name, echo.__wrapped__, (1,), {}
            )
            return set(client.zrange(index_key, 0, -1))
        finally:
            cache.purge()

    assert run(1.0) == run(100.0)
