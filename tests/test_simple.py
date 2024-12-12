from itertools import chain
from unittest import TestCase

from redis import Redis

from redcache import FifoPolicy, LfuPolicy, LruPolicy, MruPolicy, RedCache, RrPolicy

MAXSIZE = 5
TTL = 5
REDIS_URL = "redis://"


lru_cache = RedCache(__name__, LruPolicy, maxsize=MAXSIZE, redis_factory=lambda: Redis.from_url(REDIS_URL))
mru_cache = RedCache(__name__, MruPolicy, maxsize=MAXSIZE, redis_factory=lambda: Redis.from_url(REDIS_URL))
rr_cache = RedCache(__name__, RrPolicy, maxsize=MAXSIZE, redis_factory=lambda: Redis.from_url(REDIS_URL))
fifo_cache = RedCache(__name__, FifoPolicy, maxsize=MAXSIZE, redis_factory=lambda: Redis.from_url(REDIS_URL))
lfu_cache = RedCache(__name__, LfuPolicy, maxsize=MAXSIZE, redis_factory=lambda: Redis.from_url(REDIS_URL))


def _echo(x):
    return x


class SimpleTest(TestCase):
    def test_lru(self):
        @lru_cache
        def echo(x):
            return _echo(x)

        cache = lru_cache

        cache.policy.purge()

        for x in range(MAXSIZE + 1):
            for _ in range(2):
                self.assertEqual(_echo(x), echo(x))
                self.assertEqual(echo(x), echo(x))

        k0, k1 = lru_cache.policy.calc_keys()
        rc = cache.get_redis_client()

        card = rc.zcard(k0)
        hlen = rc.hlen(k1)

        self.assertEqual(card, hlen)
        self.assertEqual(card, MAXSIZE)

        members = rc.zrange(k0, 0, card - 1)
        for m in members:
            self.assertTrue(rc.hexists(k1, m))

        values = [cache.deserialize_retval(rc.hget(k1, m)) for m in members]  # type: ignore
        self.assertListEqual(sorted(values), list(range(1, 6)))

    def test_mru(self):
        cache = mru_cache
        cache.policy.purge()

        @mru_cache
        def echo(x):
            return _echo(x)

        for x in range(MAXSIZE + 1):
            for _ in range(2):
                self.assertEqual(_echo(x), echo(x))
                self.assertEqual(echo(x), echo(x))
        k0, k1 = cache.policy.calc_keys()
        rc = cache.get_redis_client()

        card = rc.zcard(k0)
        hlen = rc.hlen(k1)

        self.assertEqual(card, MAXSIZE)
        self.assertEqual(card, hlen)

        members = rc.zrange(k0, 0, card - 1)
        for m in members:
            self.assertTrue(rc.hexists(k1, m))

        values = [cache.deserialize_retval(rc.hget(k1, m)) for m in members]  # type: ignore
        self.assertListEqual(
            sorted(values),
            list(chain(range(MAXSIZE - 1), (MAXSIZE,))),
        )

    def test_rand(self):
        cache = rr_cache
        cache.policy.purge()

        @rr_cache
        def echo(x):
            return _echo(x)

        for x in range(MAXSIZE + 1):
            for _ in range(2):
                self.assertEqual(_echo(x), echo(x))
                self.assertEqual(echo(x), echo(x))

        rc = cache.get_redis_client()
        k0, k1 = cache.policy.calc_keys()

        card = rc.scard(k0)
        hlen = rc.hlen(k1)

        self.assertEqual(card, hlen)

        for m in rc.smembers(k0):
            self.assertTrue(rc.hexists(k1, m))

        self.assertEqual(card, MAXSIZE)

    def test_fifo(self):
        cache = fifo_cache
        cache.policy.purge()

        @fifo_cache
        def echo(x):
            return _echo(x)

        for x in range(MAXSIZE + 1):
            for _ in range(2):
                self.assertEqual(_echo(x), echo(x))
                self.assertEqual(echo(x), echo(x))

        k0, k1 = cache.policy.calc_keys()
        rc = cache.get_redis_client()

        card = rc.zcard(k0)
        hlen = rc.hlen(k1)

        self.assertEqual(card, MAXSIZE)
        self.assertEqual(card, hlen)

        members = rc.zrange(k0, 0, card - 1)
        for m in members:
            self.assertTrue(rc.hexists(k1, m))

        values = [cache.deserialize_retval(rc.hget(k1, m)) for m in members]  # type: ignore
        self.assertListEqual(
            sorted(values),
            list(range(1, MAXSIZE + 1)),
        )

    def test_lfu(self):
        cache = lfu_cache
        cache.policy.purge()

        @lfu_cache
        def echo(x):
            return _echo(x)

        for x in range(MAXSIZE + 1):
            self.assertEqual(_echo(x), echo(x))
            if x != 3:
                self.assertEqual(_echo(x), echo(x))

        k0, k1 = cache.policy.calc_keys()
        rc = cache.get_redis_client()

        card = rc.zcard(k0)
        hlen = rc.hlen(k1)

        self.assertEqual(card, MAXSIZE)
        self.assertEqual(card, hlen)

        members = rc.zrange(k0, 0, card - 1)
        for m in members:
            self.assertTrue(rc.hexists(k1, m))

        values = [cache.deserialize_retval(rc.hget(k1, m)) for m in members]  # type: ignore
        self.assertListEqual(
            sorted(values),
            [0, 1, 2, 4, 5],
        )
