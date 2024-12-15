import pickle
from random import randint
from unittest import TestCase
from uuid import uuid4

from redis import Redis

from redis_func_cache import FifoPolicy, LfuPolicy, LruPolicy, MruPolicy, RedisFuncCache, RrPolicy, TLruPolicy

REDIS_URL = "redis://"
SERIALIZER = pickle.dumps, pickle.loads
REDIS_FACTORY = lambda: Redis.from_url(REDIS_URL)  # noqa: E731
MAXSIZE = 8
CACHES = {
    "tlru": RedisFuncCache(__name__, TLruPolicy, redis=REDIS_FACTORY, maxsize=MAXSIZE, serializer=SERIALIZER),
    "lru": RedisFuncCache(__name__, LruPolicy, redis=REDIS_FACTORY, maxsize=MAXSIZE, serializer=SERIALIZER),
    "mru": RedisFuncCache(__name__, MruPolicy, redis=REDIS_FACTORY, maxsize=MAXSIZE, serializer=SERIALIZER),
    "rr": RedisFuncCache(__name__, RrPolicy, redis=REDIS_FACTORY, maxsize=MAXSIZE, serializer=SERIALIZER),
    "fifo": RedisFuncCache(__name__, FifoPolicy, redis=REDIS_FACTORY, maxsize=MAXSIZE, serializer=SERIALIZER),
    "lfu": RedisFuncCache(__name__, LfuPolicy, redis=REDIS_FACTORY, maxsize=MAXSIZE, serializer=SERIALIZER),
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
