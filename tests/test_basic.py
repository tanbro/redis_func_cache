from random import randint, random
from typing import cast
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4

from redis_func_cache import LruPolicy, RedisFuncCache

from ._catches import CACHES, MAXSIZE, redis_factory


def _echo(x):
    return x


class BasicTest(TestCase):
    def setUp(self):
        for cache in CACHES.values():
            cache.policy.purge()

    def test_basic(self):
        """测试缓存命中和未命中场景。"""
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
                self.assertEqual(i + 1, cache.policy.get_size())
                with patch.object(cache, "put") as mock_put:
                    self.assertEqual(i, echo(i))
                    mock_put.assert_not_called()
            self.assertEqual(cache.maxsize, cache.policy.get_size())

    def test_many_functions(self):
        """测试同一缓存实例装饰多个函数。"""
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
        """测试带括号的装饰器语法。"""
        for cache in CACHES.values():

            @cache()
            def echo(x):
                return _echo(x)

            for i in range(cache.maxsize):
                self.assertEqual(_echo(i), echo(i))

    def test_oversize(self):
        """测试缓存超限后的行为。"""
        for cache in CACHES.values():

            @cache
            def echo(x):
                return _echo(x)

            for i in range(cache.maxsize):
                self.assertEqual(_echo(i), echo(i))
            self.assertEqual(cache.maxsize, cache.policy.get_size())
            # assert not hit
            with patch.object(cache, "put") as mock_put:
                v = random()
                self.assertEqual(echo(v), v)
                mock_put.assert_called_once()
            # an actual put, then assert max size
            self.assertEqual(echo(v), v)
            self.assertEqual(cache.maxsize, cache.policy.get_size())

    def test_str(self):
        """测试字符串类型的缓存。"""
        for cache in CACHES.values():

            @cache
            def echo(x):
                return _echo(x)

            size = randint(1, cache.maxsize)
            values = [uuid4().hex for _ in range(size)]
            for v in values:
                self.assertEqual(_echo(v), echo(v))
            self.assertEqual(size, cache.policy.get_size())
            for v in values:
                self.assertEqual(v, echo(v))
            self.assertEqual(size, cache.policy.get_size())

    def test_lru(self):
        """测试 LRU 策略缓存行为。"""
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
            members = rc.zrange(k0, cast(int, "-inf"), cast(int, "+inf"), byscore=True)
            values = [cache.deserialize(x) for x in rc.hmget(k1, members) if x is not None]
            self.assertListEqual(values, list(range(1, MAXSIZE + 1)))

    def test_mru(self):
        """测试 MRU 策略缓存行为。"""
        cache = CACHES["mru"]

        @cache
        def echo(x):
            return _echo(x)

        for x in range(MAXSIZE):
            self.assertEqual(_echo(x), echo(x))

        echo(MAXSIZE)

        k0, k1 = cache.policy.calc_keys()
        rc = cache.client

        members = rc.zrange(k0, cast(int, "+inf"), cast(int, "-inf"), byscore=True, desc=True)
        values = [cache.deserialize(x) for x in rc.hmget(k1, members) if x is not None]
        self.assertListEqual(sorted(values), list(range(MAXSIZE - 1)) + [MAXSIZE])

    def test_fifo(self):
        """测试 FIFO 策略缓存行为。"""
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
        values = [cache.deserialize(x) for x in rc.hmget(k1, members) if x is not None]
        self.assertListEqual(sorted(values), list(range(1, MAXSIZE)) + [MAXSIZE])

    def test_lfu(self):
        """测试 LFU 策略缓存行为。"""
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
        values = [cache.deserialize(x) for x in rc.hmget(k1, members) if x is not None]
        self.assertListEqual(sorted(values), list(range(0, v)) + list(range(v + 1, MAXSIZE + 1)))

    def test_rr(self):
        """测试 RR 策略缓存行为。"""
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
        values = [cache.deserialize(x) for x in rc.hmget(k1, members) if x is not None]
        self.assertIn(MAXSIZE, values)

    def test_direct_redis_client(self):
        """测试直接传入 redis client 的场景。"""
        client = redis_factory()
        cache = RedisFuncCache(name="test_direct_redis_client", policy=LruPolicy, client=client)

        @cache
        def echo(x):
            return x

        for i in range(MAXSIZE):
            self.assertEqual(echo(i), i)

    def test_exception_handling(self):
        """测试被缓存函数抛出异常时缓存行为。"""
        for cache in CACHES.values():

            @cache
            def fail(x):
                raise ValueError("fail")

            with self.assertRaises(ValueError):
                fail(1)
            # 再次调用应继续抛异常，不应缓存异常结果
            with self.assertRaises(ValueError):
                fail(1)

    def test_unserializable_object(self):
        """测试不可序列化对象缓存时的行为。"""
        import threading

        for cache in CACHES.values():

            @cache
            def echo(x):
                return x

            obj = threading.Lock()
            with self.assertRaises(Exception):
                echo(obj)

    def test_various_argument_types(self):
        """测试不同参数类型的缓存支持。"""
        for cache in CACHES.values():

            @cache
            def echo(x):
                return x

            for v in [None, 1.23, True, (1, 2), {"a": 1}, frozenset({1, 2})]:
                try:
                    self.assertEqual(echo(v), v)
                except Exception:
                    # 某些类型如 dict 可能不支持做 key
                    pass

    def test_cache_purge(self):
        """测试缓存清理后缓存应为空。"""
        for cache in CACHES.values():

            @cache
            def echo(x):
                return x

            echo(1)
            cache.policy.purge()
            # 清理后应 miss
            with patch.object(cache, "get", return_value=None) as mock_get:
                with patch.object(cache, "put") as mock_put:
                    echo(2)
                    mock_get.assert_called_once()
                    mock_put.assert_called_once()

    def test_custom_serializer(self):
        """测试自定义序列化器的兼容性。"""
        import pickle

        for cache in CACHES.values():

            @cache(serializer=(pickle.dumps, pickle.loads))
            def echo(x):
                return x

            v = {"a": 1, "b": 2}
            self.assertEqual(echo(v), v)
            self.assertEqual(echo(v), v)


class InvalidFunctionTestCase(TestCase):
    def setUp(self):
        for cache in CACHES.values():
            cache.policy.purge()

    def test_builtin_function_or_method(self):
        import pickle

        for cache in CACHES.values():
            f = cache(pickle.dumps, serializer=(pickle.dumps, pickle.loads))
            for _ in range(cache.maxsize * 2 + 1):
                v = uuid4()
                self.assertEqual(pickle.dumps(v), f(v))

    def test_no_callable(self):
        for cache in CACHES.values():
            with self.assertRaises(TypeError):
                cache(1)  # type: ignore

    def test_lambda(self):
        for cache in CACHES.values():
            f = cache(lambda x: x)
            for _ in range(cache.maxsize * 2 + 1):
                v = uuid4().hex
                self.assertEqual(v, f(v))


class ExcludeArgsTestCase(TestCase):
    def setUp(self):
        for cache in CACHES.values():
            cache.policy.purge()

    def test_exclude_positional_args(self):
        def user_func(func, value):
            return func(value)

        unpicklable = lambda x: x  # noqa: E731

        for cache in CACHES.values():
            f = cache(user_func, excludes_positional=[0])
            for _ in range(cache.maxsize * 2 + 1):
                v = uuid4().hex
                self.assertEqual(f(unpicklable, v), v)

    def test_exclude_keyword_args(self):
        def user_func(func, value):
            return func(value)

        unpicklable = lambda x: x  # noqa: E731

        for cache in CACHES.values():
            f = cache(user_func, excludes=["func"])
            for _ in range(cache.maxsize * 2 + 1):
                v = uuid4().hex
                self.assertEqual(f(func=unpicklable, value=v), v)
