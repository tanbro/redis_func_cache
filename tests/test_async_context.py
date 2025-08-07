import asyncio
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from ._catches import ASYNC_CACHES, close_all_async_resources


class AsyncContextTTLTest(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        coros = (cache.policy.apurge() for cache in ASYNC_CACHES.values())
        await asyncio.gather(*coros)

    async def asyncTearDown(self):
        # 正确关闭所有异步Redis客户端连接，防止"Event loop is closed"错误
        await asyncio.gather(*(cache.client.close() for cache in ASYNC_CACHES.values()))

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
            with cache.disabled():
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


# 模块级别的清理函数，在所有测试运行完毕后调用
def tearDownModule():
    """在模块中的所有测试运行完毕后清理异步资源"""
    try:
        # 获取当前事件循环
        loop = asyncio.get_event_loop()
        # 如果事件循环还在运行，则执行清理
        if loop.is_running():
            loop.create_task(close_all_async_resources())
        else:
            # 否则直接运行直到完成
            loop.run_until_complete(close_all_async_resources())
    except RuntimeError:
        # 如果没有事件循环或者事件循环已关闭，忽略错误
        pass
