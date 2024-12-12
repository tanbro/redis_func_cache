from itertools import chain
from random import randint
from time import sleep
from unittest import TestCase
from unittest.mock import patch

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
        cache = lru_cache

        @cache
        def echo(x):
            return _echo(x)

        cache.policy.purge()

        for x in range(MAXSIZE + 1):
            self.assertEqual(_echo(x), echo(x))
            echo(x)
            self.assertEqual(echo(x), echo(x))
            with (
                patch.object(cache, "exec_get_script", return_value=cache.serialize_return_value(x)) as mock_get,
                patch.object(cache, "exec_put_script") as mock_put,
            ):
                self.assertEqual(echo(x), x)
                mock_get.assert_called_once()
                mock_put.assert_not_called()
            with (
                patch.object(cache, "exec_get_script", return_value=None) as mock_get,
                patch.object(cache, "exec_put_script") as mock_put,
            ):
                echo(x)
                mock_get.assert_called_once()
                mock_put.assert_called_once()
            sleep(0.001)

        k0, k1 = cache.policy.calc_keys()
        rc = cache.get_redis_client()

        card = rc.zcard(k0)
        hlen = rc.hlen(k1)

        self.assertEqual(card, hlen)
        self.assertEqual(card, MAXSIZE)

        members = rc.zrange(k0, 0, card - 1)
        for m in members:
            self.assertTrue(rc.hexists(k1, m))

        values = [cache.deserialize_return_value(rc.hget(k1, m)) for m in members]  # type: ignore
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
            sleep(0.001)

        k0, k1 = cache.policy.calc_keys()
        rc = cache.get_redis_client()

        card = rc.zcard(k0)
        hlen = rc.hlen(k1)

        self.assertEqual(card, MAXSIZE)
        self.assertEqual(card, hlen)

        members = rc.zrange(k0, 0, card - 1)
        for m in members:
            self.assertTrue(rc.hexists(k1, m))

        values = [cache.deserialize_return_value(rc.hget(k1, m)) for m in members]  # type: ignore
        self.assertListEqual(
            sorted(values),
            list(chain(range(MAXSIZE - 1), (MAXSIZE,))),
        )

    def test_rr(self):
        cache = rr_cache
        cache.policy.purge()

        @rr_cache
        def echo(x):
            return _echo(x)

        for x in range(MAXSIZE + 1):
            for _ in range(2):
                self.assertEqual(_echo(x), echo(x))
                self.assertEqual(echo(x), echo(x))
            sleep(0.001)

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
            sleep(0.001)

        k0, k1 = cache.policy.calc_keys()
        rc = cache.get_redis_client()

        card = rc.zcard(k0)
        hlen = rc.hlen(k1)

        self.assertEqual(card, MAXSIZE)
        self.assertEqual(card, hlen)

        members = rc.zrange(k0, 0, card - 1)
        for m in members:
            self.assertTrue(rc.hexists(k1, m))

        values = [cache.deserialize_return_value(rc.hget(k1, m)) for m in members]  # type: ignore
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

        n_ignore = randint(0, MAXSIZE - 1)

        for x in range(MAXSIZE + 1):
            self.assertEqual(_echo(x), echo(x))
            if x != n_ignore:
                self.assertEqual(_echo(x), echo(x))
            sleep(0.001)

        k0, k1 = cache.policy.calc_keys()
        rc = cache.get_redis_client()

        card = rc.zcard(k0)
        hlen = rc.hlen(k1)

        self.assertEqual(card, MAXSIZE)
        self.assertEqual(card, hlen)

        members = rc.zrange(k0, 0, card - 1)
        for m in members:
            self.assertTrue(rc.hexists(k1, m))

        values = [cache.deserialize_return_value(rc.hget(k1, m)) for m in members]  # type: ignore
        self.assertListEqual(
            sorted(values),
            list(chain(range(0, n_ignore), range(n_ignore + 1, MAXSIZE + 1))),
        )
