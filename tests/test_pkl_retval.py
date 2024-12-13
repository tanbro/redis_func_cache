import pickle
from random import randint
from unittest import TestCase
from uuid import uuid4

from redis import Redis

from redcache import FifoPolicy, LfuPolicy, LruPolicy, MruPolicy, RedCache, RrPolicy

REDIS_URL = "redis://"
SERIALIZER = pickle.dumps, pickle.loads
REDIS_FACTORY = lambda: Redis.from_url(REDIS_URL)  # noqa: E731
MAXSIZE = 8
CACHES = {
    "lru": RedCache(__name__, LruPolicy, redis_factory=REDIS_FACTORY, maxsize=MAXSIZE, serializer=SERIALIZER),
    "mru": RedCache(__name__, MruPolicy, redis_factory=REDIS_FACTORY, maxsize=MAXSIZE, serializer=SERIALIZER),
    "rr": RedCache(__name__, RrPolicy, redis_factory=REDIS_FACTORY, maxsize=MAXSIZE, serializer=SERIALIZER),
    "fifo": RedCache(__name__, FifoPolicy, redis_factory=REDIS_FACTORY, maxsize=MAXSIZE, serializer=SERIALIZER),
    "lfu": RedCache(__name__, LfuPolicy, redis_factory=REDIS_FACTORY, maxsize=MAXSIZE, serializer=SERIALIZER),
}


class MyObject:
    def __init__(self, value):
        self.value = value

    def __eq__(self, value: object) -> bool:
        return self.value == value


class PklRetvalTest(TestCase):
    def setUp(self):
        for cache in CACHES.values():
            cache.policy.purge()

    def test_object(self):
        for cache in CACHES.values():

            @cache
            def echo(o):
                return o

            for _ in range(randint(1, MAXSIZE * 2)):
                obj = MyObject(uuid4())
                self.assertEqual(obj, echo(obj))
                self.assertEqual(obj, echo(obj))
