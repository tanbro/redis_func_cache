import asyncio
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from ._catches import ASYNC_CACHES


class AsyncContextTTLTest(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        coros = (cache.policy.apurge() for cache in ASYNC_CACHES.values())
        await asyncio.gather(*coros)

    async def test_async_ttl_contextual(self):
        for cache in ASYNC_CACHES.values():

            @cache
            async def echo(x):
                await asyncio.sleep(0)
                return x

            val = uuid4().hex

            # 正常调用，缓存应生效
            self.assertEqual(await echo(val), val)
            with patch.object(cache, "aput", side_effect=AsyncMock()) as mock_put:
                self.assertEqual(await echo(val), val)
                mock_put.assert_not_called()

            # 再次调用，缓存应失效，触发写入
            with cache.disable():
                with patch.object(cache, "aget", side_effect=AsyncMock(return_value=None)) as mock_get:
                    with patch.object(cache, "aput", side_effect=AsyncMock()) as mock_put:
                        result = await echo(val)
                        mock_get.assert_not_called()
                        mock_put.assert_not_called()
                        self.assertEqual(result, val)

            # 离开上下文后，缓存应恢复正常
            with patch.object(cache, "aget", side_effect=AsyncMock(return_value=cache.serialize(val))) as mock_get:
                with patch.object(cache, "aput", side_effect=AsyncMock()) as mock_put:
                    result = await echo(val)
                    mock_get.assert_called_once()
                    mock_put.assert_not_called()
                    self.assertEqual(result, val)
