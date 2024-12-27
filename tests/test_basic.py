from random import randint, random
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4

from redis_func_cache import LruPolicy, RedisFuncCache

from ._catches import CACHES, MAXSIZE, REDIS_FACTORY


def _echo(x):
    return x


class BasicTest(TestCase):
    def setUp(self):
        for cache in CACHES.values():
            cache.policy.purge()

    def test_basic(self):
        for cache in CACHES.values():

            @cache
            def echo(x):
                return _echo(x)

            # mock hit
            for i in range(cache.maxsize):
                with patch.object(cache, "get", return_value=cache.serialize(i)) as mock_get:
                    with patch.object(cache, "put") as mock_put:
                        echo(i)
                        mock_get.assert_called_once()
                        mock_put.assert_not_called()

            # mock not hit
            for i in range(cache.maxsize):
                with patch.object(cache, "get", return_value=None) as mock_get:
                    with patch.object(cache, "put") as mock_put:
                        echo(i)
                        mock_get.assert_called_once()
                        mock_put.assert_called_once()

            # first run, fill the cache to max size. then second run, to hit the cache
            for i in range(cache.maxsize):
                self.assertEqual(_echo(i), echo(i))
                self.assertEqual(i + 1, cache.policy.size())
                with patch.object(cache, "put") as mock_put:
                    self.assertEqual(i, echo(i))
                    mock_put.assert_not_called()
            self.assertEqual(cache.maxsize, cache.policy.size())

    def test_many_functions(self):
        for cache in CACHES.values():

            @cache()
            def echo1(x):
                return x

            @cache()
            def echo2(x):
                return x

            for a, b in zip(range(cache.maxsize), range(cache.maxsize - 1, -1, -1)):
                echo1(a)
                echo2(b)
                with patch.object(cache, "get", return_value=None) as mock_get:
                    with patch.object(cache, "put") as mock_put:
                        echo1(b)
                        mock_get.assert_called_once()
                        mock_put.assert_called_once()
                with patch.object(cache, "get", return_value=None) as mock_get:
                    with patch.object(cache, "put") as mock_put:
                        echo2(a)
                        mock_get.assert_called_once()
                        mock_put.assert_called_once()

    def test_parenthesis(self):
        for cache in CACHES.values():

            @cache()
            def echo(x):
                return _echo(x)

            for i in range(cache.maxsize):
                self.assertEqual(_echo(i), echo(i))

    def test_oversize(self):
        for cache in CACHES.values():

            @cache
            def echo(x):
                return _echo(x)

            for i in range(cache.maxsize):
                self.assertEqual(_echo(i), echo(i))
            self.assertEqual(cache.maxsize, cache.policy.size())
            # assert not hit
            with patch.object(cache, "put") as mock_put:
                v = random()
                self.assertEqual(echo(v), v)
                mock_put.assert_called_once()
            # an actual put, then assert max size
            self.assertEqual(echo(v), v)
            self.assertEqual(cache.maxsize, cache.policy.size())

    def test_str(self):
        for cache in CACHES.values():

            @cache
            def echo(x):
                return _echo(x)

            size = randint(1, cache.maxsize)
            values = [uuid4().hex for _ in range(size)]
            for v in values:
                self.assertEqual(_echo(v), echo(v))
            self.assertEqual(size, cache.policy.size())
            for v in values:
                self.assertEqual(v, echo(v))
            self.assertEqual(size, cache.policy.size())

    def test_lru(self):
        for name_, cache in CACHES.items():
            if name_ not in ("lru", "tru"):
                continue

            @cache
            def echo(x):
                return _echo(x)

            for x in range(MAXSIZE):
                self.assertEqual(_echo(x), echo(x))

            echo(MAXSIZE)

            k0, k1 = cache.policy.calc_keys()
            rc = cache.client

            card = rc.zcard(k0)
            self.assertEqual(card, MAXSIZE)
            members = rc.zrange(k0, "-inf", "+inf", byscore=True)  # type: ignore
            values = [cache.deserialize(x) for x in rc.hmget(k1, members)]  # type: ignore
            self.assertListEqual(values, list(range(1, MAXSIZE + 1)))

    def test_mru(self):
        cache = CACHES["mru"]

        @cache
        def echo(x):
            return _echo(x)

        for x in range(MAXSIZE):
            self.assertEqual(_echo(x), echo(x))

        echo(MAXSIZE)

        k0, k1 = cache.policy.calc_keys()
        rc = cache.client

        members = rc.zrange(k0, "+inf", "-inf", byscore=True, desc=True)  # type: ignore
        values = [cache.deserialize(x) for x in rc.hmget(k1, members)]  # type: ignore
        self.assertListEqual(sorted(values), list(range(MAXSIZE - 1)) + [MAXSIZE])

    def test_fifo(self):
        cache = CACHES["fifo"]

        @cache
        def echo(x):
            return _echo(x)

        for x in range(MAXSIZE):
            self.assertEqual(_echo(x), echo(x))

        for _ in range(MAXSIZE):
            v = randint(0, MAXSIZE - 1)
            echo(v)

        echo(MAXSIZE)

        k0, k1 = cache.policy.calc_keys()
        rc = cache.client

        card = rc.zcard(k0)
        members = rc.zrange(k0, 0, card - 1)
        values = [cache.deserialize(x) for x in rc.hmget(k1, members)]  # type: ignore
        self.assertListEqual(sorted(values), list(range(1, MAXSIZE)) + [MAXSIZE])

    def test_lfu(self):
        cache = CACHES["lfu"]

        @cache
        def echo(x):
            return _echo(x)

        for x in range(MAXSIZE):
            self.assertEqual(_echo(x), echo(x))

        v = randint(0, MAXSIZE - 1)
        for i in range(MAXSIZE):
            if i != v:
                echo(i)

        echo(MAXSIZE)

        k0, k1 = cache.policy.calc_keys()
        rc = cache.client

        card = rc.zcard(k0)
        members = rc.zrange(k0, 0, card - 1)
        values = [cache.deserialize(x) for x in rc.hmget(k1, members)]  # type: ignore
        self.assertListEqual(sorted(values), list(range(0, v)) + list(range(v + 1, MAXSIZE + 1)))

    def test_rr(self):
        cache = CACHES["rr"]

        @cache
        def echo(x):
            return _echo(x)

        for x in range(MAXSIZE):
            self.assertEqual(_echo(x), echo(x))

        for _ in range(MAXSIZE):
            v = randint(0, MAXSIZE - 1)
            echo(v)

        echo(MAXSIZE)

        k0, k1 = cache.policy.calc_keys()
        rc = cache.client

        members = rc.smembers(k0)
        values = [cache.deserialize(x) for x in rc.hmget(k1, members)]  # type: ignore
        self.assertIn(MAXSIZE, values)

    def test_direct_redis_client(self):
        client = REDIS_FACTORY()
        cache = RedisFuncCache(name="test_direct_redis_client", policy=LruPolicy, client=client)

        @cache
        def echo(x):
            return x

        for i in range(MAXSIZE):
            self.assertEqual(echo(i), i)
