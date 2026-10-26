"""The ``**options`` extension point of ``cache(...)``: what forwarding really guarantees.

Decorator kwargs beyond the named parameters are **not** validated: they ride
into the ARGV options JSON and are read only by the one policy that names them
(``cost`` for GDSF, ``reject_p`` for the ``lru_tr`` family). That permissive
behavior is a deliberate trade-off — a custom
:class:`~redis_func_cache.scripts.Scripts` subclass may consume any option it
wants — and it is what these tests pin, including the two edges the design
accepts:

- an option no policy consumes is ignored silently (a misspelled ``cost`` is a
  cache that quietly runs with the default cost, not an error);
- an option that is not JSON-encodable fails on the **read** path, before the
  wrapped function ever runs, and that failure is not a
  :class:`redis.exceptions.RedisError` — so :attr:`ignore_redis_errors` does
  not cover it.
"""

from __future__ import annotations

import math

import pytest

from redis_func_cache import RedisFuncCache, gdsf_policy, lru_policy, lru_t_policy
from redis_func_cache.scripts import GdsfScripts

from ._catches import redis_factory

_UNENCODABLE = object()


@pytest.fixture()
def cache():
    cache = RedisFuncCache(__name__, lru_policy, factory=redis_factory, maxsize=3)
    cache.purge()
    yield cache
    cache.purge()


class TestPermissiveForwarding:
    """Unknown keys are accepted and ignored — the documented extension point."""

    def test_stray_option_is_silently_ignored(self, cache):
        """A key no policy consumes does not raise, and the cache still works.

        The trade-off: ``cots`` looks like ``cost``, lands in the options JSON,
        and nothing reads it. The call succeeds and the entry is stored — no
        signal of any kind that the user's intent was dropped.
        """

        @cache.decorate(cots=5)
        def echo(x):
            return x

        assert echo(1) == 1
        assert cache.get_size() == 1

    def test_option_meant_for_another_policy_is_ignored(self, cache):
        """``cost`` on a non-GDSF policy changes nothing and says nothing."""

        @cache.decorate(cost=100.0)
        def echo(x):
            return x

        assert echo(1) == 1
        (index_key, value_key), hash_value = cache.policy.locate(cache.prefix, cache.name, echo.__wrapped__, (1,), {})
        client = redis_factory()
        member = hash_value.encode() if isinstance(hash_value, str) else hash_value
        # Two signals that the LRU script ran and never saw the cost: the index
        # holds LRU's insertion order (the first entry is exactly 1, where a cost
        # score would be ``1 * 100 / size``), and the value hash has no ``:m``
        # metadata field — only the cost-aware scripts write one.
        assert client.zscore(index_key, member) == 1
        assert client.hexists(value_key, member + b":m") == 0

    def test_declared_option_reaches_its_own_scripts(self):
        """The counterpart: ``cost`` is consumed by GDSF, and coercibly."""
        assert GdsfScripts().calc_ext_args(options={"cost": "2"}) == (2.0,)
        assert GdsfScripts().calc_ext_args(options={}) == (1.0,)  # absent → default


class TestUnencodableOption:
    """The sharp edge: a value that cannot be JSON-encoded breaks the read path."""

    def test_breaks_before_the_function_runs(self):
        """The raise comes from the get script's ARGV assembly, so the body never executes."""
        cache = RedisFuncCache("unencodable_read", lru_policy, factory=redis_factory)
        cache.purge()
        executed = []

        @cache.decorate(junk=_UNENCODABLE)
        def f(x):
            executed.append(x)
            return x

        with pytest.raises(TypeError, match="not JSON serializable"):
            f(1)
        assert executed == []  # the read path is reached before the call
        cache.purge()

    def test_ignore_redis_errors_does_not_cover_it(self):
        """``ignore_redis_errors=True`` promises graceful degradation for Redis failures only.

        The options JSON is serialized client-side, so its ``TypeError`` is not
        a :class:`RedisError` and survives the degrade path: the caller gets an
        exception where a Redis outage would have returned a fresh value.
        """
        cache = RedisFuncCache("unencodable_degrade", lru_policy, factory=redis_factory, ignore_redis_errors=True)
        cache.purge()
        executed = []

        @cache.decorate(junk=_UNENCODABLE)
        def f(x):
            executed.append(x)
            return x

        with pytest.raises(TypeError, match="not JSON serializable"):
            f(1)
        assert executed == []
        cache.purge()


class TestCostValueRange:
    """What the GDSF value guard covers, and the one thing it does not."""

    def test_infinite_cost_is_accepted_by_the_python_guard(self):
        """The guard rejects NaN and non-positive; ``inf`` passes both checks.

        Pinned as current behavior: ``isnan`` is the only non-finite test in
        :meth:`GdsfScripts.calc_ext_args`, so ``inf`` is coerced and shipped.
        """
        assert GdsfScripts().calc_ext_args(options={"cost": math.inf}) == (math.inf,)

    def test_infinite_cost_end_to_end(self):
        """Redis accepts an infinite ZSET score, so an ``inf`` cost is stored as-is.

        This is the consequence, not a hypothetical: the score goes in as
        ``inf`` and the metadata round-trips as ``"1 inf"``.
        """
        cache = RedisFuncCache("inf_cost", gdsf_policy, factory=redis_factory, maxsize=2)
        cache.purge()

        @cache.decorate(cost=math.inf)
        def f(x):
            return f"v{x}"

        assert f(1) == "v1"
        client = redis_factory()
        (index_key, value_key), hash_value = cache.policy.locate(cache.prefix, cache.name, f.__wrapped__, (1,), {})
        member = hash_value.encode() if isinstance(hash_value, str) else hash_value
        assert client.zscore(index_key, member) == math.inf
        assert client.hget(value_key, member + b":m") == b"1 inf"
        cache.purge()

    def test_infinite_cost_makes_the_entry_unevictable(self):
        """The eviction consequence the NaN guard exists to prevent.

        ``GdsfScripts.calc_ext_args`` rejects NaN because "a zero cost would
        make every score zero and eviction degenerate". ``inf`` is the mirror
        image of that and passes the guard: eviction is ZPOPMIN (lowest score
        first), so an infinite score is never popped — the entry survives any
        number of later insertions and holds its slot in the pair forever.
        """
        cache = RedisFuncCache("inf_evict", gdsf_policy, factory=redis_factory, maxsize=2)
        cache.purge()

        @cache.decorate(cost=math.inf)
        def sticky(x):
            return f"s{x}"

        @cache.decorate(cost=1.0)
        def normal(x):
            return f"n{x}"

        sticky(1)  # one entry with an infinite score, in a pair of maxsize 2
        for i in range(2, 8):
            normal(i)  # plenty of pressure to evict it, if scores were finite

        client = redis_factory()
        (index_key, sticky_value_key), sticky_member = cache.policy.locate(
            cache.prefix, cache.name, sticky.__wrapped__, (1,), {}
        )
        member = sticky_member.encode() if isinstance(sticky_member, str) else sticky_member
        assert client.zscore(index_key, member) == math.inf
        assert client.hexists(sticky_value_key, member)  # never evicted
        assert client.zcard(index_key) == 2  # the pair is capped, so others paid for it
        cache.purge()


class TestNothingElseConsumesOptions:
    """No built-in get/put script reads the options JSON — it is a reserved slot."""

    def test_options_do_not_change_lru_t_behavior(self):
        """The same calls with and without an option produce the same cache state."""

        def populate(name: str, **kwds):
            cache = RedisFuncCache(name, lru_t_policy, factory=redis_factory, maxsize=3)
            cache.purge()

            @cache.decorate(**kwds)
            def echo(x):
                return x

            echo(1)
            echo(2)
            (index_key, _), _ = cache.policy.locate(cache.prefix, cache.name, echo.__wrapped__, (1,), {})
            client = redis_factory()
            members = client.zrange(index_key, 0, -1)
            cache.purge()
            return members

        assert populate("plain_lru_t") == populate("noisy_lru_t", whatever_option="ignored")
