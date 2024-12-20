import asyncio
from os import getenv
from random import randint
from unittest import IsolatedAsyncioTestCase

from redis.asyncio import Redis

from redis_func_cache import FifoPolicy, LfuPolicy, LruPolicy, LruTPolicy, MruPolicy, RedisFuncCache, RrPolicy

REDIS_URL = getenv("REDIS_URL", "redis://")
REDIS_FACTORY = lambda: Redis.from_url(REDIS_URL)  # noqa: E731
MAXSIZE = 8
CACHES = {
    "tlru": RedisFuncCache(__name__, LruTPolicy, client=REDIS_FACTORY, maxsize=MAXSIZE),
    "lru": RedisFuncCache(__name__, LruPolicy, client=REDIS_FACTORY, maxsize=MAXSIZE),
    "mru": RedisFuncCache(__name__, MruPolicy, client=REDIS_FACTORY, maxsize=MAXSIZE),
    "rr": RedisFuncCache(__name__, RrPolicy, client=REDIS_FACTORY, maxsize=MAXSIZE),
    "fifo": RedisFuncCache(__name__, FifoPolicy, client=REDIS_FACTORY, maxsize=MAXSIZE),
    "lfu": RedisFuncCache(__name__, LfuPolicy, client=REDIS_FACTORY, maxsize=MAXSIZE),
}


def _echo(x):
    return x


class BasicTest(IsolatedAsyncioTestCase):
    async def setUp(self):
        for cache in CACHES.values():
            await cache.policy.apurge()

    async def test_simple(self):
        for cache in CACHES.values():

            @cache
            async def echo(x):
                await asyncio.sleep(0)
                return _echo(x)

            n = randint(cache.maxsize + 1, 2 * cache.maxsize)
            for i in range(n):
                self.assertEqual(i, await echo(i))
                self.assertEqual(i, await echo(i))

            self.assertEqual(cache.maxsize, await cache.policy.asize())
