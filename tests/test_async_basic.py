import asyncio
from random import randint
from unittest import IsolatedAsyncioTestCase

from ._catches import ASYNC_CACHES


def _echo(x):
    return x


class BasicTest(IsolatedAsyncioTestCase):
    async def setUp(self):
        for cache in ASYNC_CACHES.values():
            await cache.policy.apurge()

    async def test_simple(self):
        for cache in ASYNC_CACHES.values():

            @cache
            async def echo(x):
                await asyncio.sleep(0)
                return _echo(x)

            n = randint(cache.maxsize + 1, 2 * cache.maxsize)
            for i in range(n):
                self.assertEqual(i, await echo(i))
                self.assertEqual(i, await echo(i))

            self.assertEqual(cache.maxsize, await cache.policy.asize())
