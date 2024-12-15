from random import randint
from unittest import TestCase

from redis import Redis

from redis_func_cache import (
    FifoMultiplePolicy,
    LfuMultiplePolicy,
    LruMultiplePolicy,
    MruMultiplePolicy,
    RedisFuncCache,
    RrMultiplePolicy,
    TLruMultiplePolicy,
)

REDIS_URL = "redis://"
REDIS_FACTORY = lambda: Redis.from_url(REDIS_URL)  # noqa: E731
MAXSIZE = 8
CACHES = {
    "tlru": RedisFuncCache(__name__, TLruMultiplePolicy, redis=REDIS_FACTORY, maxsize=MAXSIZE),
    "lru": RedisFuncCache(__name__, LruMultiplePolicy, redis=REDIS_FACTORY, maxsize=MAXSIZE),
    "mru": RedisFuncCache(__name__, MruMultiplePolicy, redis=REDIS_FACTORY, maxsize=MAXSIZE),
    "rr": RedisFuncCache(__name__, RrMultiplePolicy, redis=REDIS_FACTORY, maxsize=MAXSIZE),
    "fifo": RedisFuncCache(__name__, FifoMultiplePolicy, redis=REDIS_FACTORY, maxsize=MAXSIZE),
    "lfu": RedisFuncCache(__name__, LfuMultiplePolicy, redis=REDIS_FACTORY, maxsize=MAXSIZE),
}


class MultipleTest(TestCase):
    def setUp(self):
        for cache in CACHES.values():
            cache.policy.purge()

    def test_int(self):
        for cache in CACHES.values():

            @cache
            def echo(x):
                return x

            for i in range(randint(1, MAXSIZE * 2)):
                self.assertEqual(i, echo(i))
                self.assertEqual(i, echo(i))

    def test_two_functions(self):
        for cache in CACHES.values():

            @cache
            def echo1(x):
                return x

            @cache
            def echo2(x):
                return x

            for i in range(randint(MAXSIZE, MAXSIZE * 2)):
                self.assertEqual(i, echo1(i))
                self.assertEqual(i, echo2(i))
