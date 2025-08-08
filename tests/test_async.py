import asyncio
from random import randint
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from ._catches import ASYNC_CACHES, ASYNC_MULTI_CACHES, CACHES


def _echo(x):
    return x


class AsyncTest(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        coros = (cache.policy.apurge() for cache in ASYNC_CACHES.values())
        await asyncio.gather(*coros)

    async def asyncTearDown(self):
        # 清理异步Redis客户端连接
        for cache in ASYNC_CACHES.values():
            if hasattr(cache.client, "aclose"):
                await cache.client.aclose()
            elif hasattr(cache.client, "close"):
                await cache.client.close()

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

            self.assertEqual(cache.maxsize, await cache.policy.aget_size())


class AsyncMultiTest(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        coros = (cache.policy.apurge() for cache in ASYNC_MULTI_CACHES.values())
        await asyncio.gather(*coros)

    async def asyncTearDown(self):
        # 清理异步Redis客户端连接
        for cache in ASYNC_MULTI_CACHES.values():
            if hasattr(cache.client, "aclose"):
                await cache.client.aclose()
            elif hasattr(cache.client, "close"):
                await cache.client.close()

    async def test_simple(self):
        for cache in ASYNC_MULTI_CACHES.values():

            @cache
            async def echo1(x):
                await asyncio.sleep(0)
                return _echo(x)

            @cache
            async def echo2(x):
                await asyncio.sleep(0)
                return _echo(x)

            n = randint(cache.maxsize + 1, 2 * cache.maxsize)
            for i in range(n):
                self.assertEqual(i, await echo1(i))
                self.assertEqual(i, await echo2(i))
                self.assertEqual(i, await echo1(i))
                self.assertEqual(i, await echo2(i))

    async def test_missing(self):
        for cache in ASYNC_MULTI_CACHES.values():

            @cache
            async def echo1(x):
                await asyncio.sleep(0)
                return _echo(x)

            @cache
            async def echo2(x):
                await asyncio.sleep(0)
                return _echo(x)

            n = randint(cache.maxsize // 2 + 1, cache.maxsize + 1)
            for i in range(n):
                with patch.object(cache, "aget", side_effect=AsyncMock(return_value=cache.serialize(i))) as mock_get:
                    with patch.object(cache, "aput", side_effect=AsyncMock()) as mock_put:
                        await echo1(i)
                        mock_get.assert_called_once()
                        mock_put.assert_not_called()
                with patch.object(cache, "aget", side_effect=AsyncMock(return_value=cache.serialize(i))) as mock_get:
                    with patch.object(cache, "aput", side_effect=AsyncMock()) as mock_put:
                        await echo2(i)
                        mock_get.assert_called_once()
                        mock_put.assert_not_called()

    def test_type_error_async_for_sync(self):
        for cache in ASYNC_CACHES.values():
            with self.assertRaises(TypeError):

                @cache
                def _(x):
                    return x

    async def test_type_error_sync_for_async(self):
        for cache in CACHES.values():
            with self.assertRaises(TypeError):

                @cache
                async def _(x):
                    await asyncio.sleep(0)
                    return x
