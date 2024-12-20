from os import getenv
from random import randint
from unittest import TestCase

from redis import Redis

from redis_func_cache import (
    FifoClusterMultiplePolicy,
    LfuClusterMultiplePolicy,
    LruClusterMultiplePolicy,
    LruTClusterMultiplePolicy,
    MruClusterMultiplePolicy,
    RedisFuncCache,
    RrClusterMultiplePolicy,
)

REDIS_URL = getenv("REDIS_URL", "redis://")
REDIS_FACTORY = lambda: Redis.from_url(REDIS_URL)  # noqa: E731
MAXSIZE = 8
CACHES = {
    "tlru": RedisFuncCache(__name__, LruTClusterMultiplePolicy, client=REDIS_FACTORY, maxsize=MAXSIZE),
    "lru": RedisFuncCache(__name__, LruClusterMultiplePolicy, client=REDIS_FACTORY, maxsize=MAXSIZE),
    "mru": RedisFuncCache(__name__, MruClusterMultiplePolicy, client=REDIS_FACTORY, maxsize=MAXSIZE),
    "rr": RedisFuncCache(__name__, RrClusterMultiplePolicy, client=REDIS_FACTORY, maxsize=MAXSIZE),
    "fifo": RedisFuncCache(__name__, FifoClusterMultiplePolicy, client=REDIS_FACTORY, maxsize=MAXSIZE),
    "lfu": RedisFuncCache(__name__, LfuClusterMultiplePolicy, client=REDIS_FACTORY, maxsize=MAXSIZE),
}


class ClusterMultipleTest(TestCase):
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
