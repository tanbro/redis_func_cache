import pickle
from random import randint
from unittest import TestCase

from redis import Redis

from redcache import FifoClusterPolicy, LfuClusterPolicy, LruClusterPolicy, MruClusterPolicy, RedCache, RrClusterPolicy

REDIS_URL = "redis://"
SERIALIZER = pickle.dumps, pickle.loads
REDIS_FACTORY = lambda: Redis.from_url(REDIS_URL)  # noqa: E731
MAXSIZE = 8
CACHES = {
    "lru": RedCache(__name__, LruClusterPolicy, redis_factory=REDIS_FACTORY, maxsize=MAXSIZE, serializer=SERIALIZER),
    "mru": RedCache(__name__, MruClusterPolicy, redis_factory=REDIS_FACTORY, maxsize=MAXSIZE, serializer=SERIALIZER),
    "rr": RedCache(__name__, RrClusterPolicy, redis_factory=REDIS_FACTORY, maxsize=MAXSIZE, serializer=SERIALIZER),
    "fifo": RedCache(__name__, FifoClusterPolicy, redis_factory=REDIS_FACTORY, maxsize=MAXSIZE, serializer=SERIALIZER),
    "lfu": RedCache(__name__, LfuClusterPolicy, redis_factory=REDIS_FACTORY, maxsize=MAXSIZE, serializer=SERIALIZER),
}


class ClusterTest(TestCase):
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
