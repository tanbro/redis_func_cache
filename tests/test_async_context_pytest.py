import asyncio
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from redis.asyncio import Redis as AsyncRedis

from redis_func_cache import LruTPolicy, RedisFuncCache


@pytest.fixture
def async_redis_client():
    """创建独立的异步Redis客户端"""
    client = AsyncRedis.from_url("redis://localhost")
    yield client
    # 清理客户端
    try:
        loop = asyncio.get_event_loop()
        if not loop.is_closed():
            if hasattr(client, "aclose"):
                loop.run_until_complete(client.aclose())
            else:
                loop.run_until_complete(client.close())
    except Exception:
        pass


@pytest.fixture
def cache(async_redis_client):
    """创建独立的缓存实例"""
    cache_instance = RedisFuncCache(__name__, LruTPolicy, client=lambda: async_redis_client, maxsize=8)
    yield cache_instance
    # 清理缓存
    try:
        loop = asyncio.get_event_loop()
        if not loop.is_closed():
            loop.run_until_complete(cache_instance.policy.apurge())
    except Exception:
        pass


class TestAsyncContext:
    @pytest.mark.asyncio
    async def test_async_ttl_contextual(self, cache):
        @cache
        async def echo(x):
            await asyncio.sleep(0)
            return x

        val = uuid4().hex

        # 正常调用，缓存应生效
        assert await echo(val) == val
        with patch.object(cache, "aput", side_effect=AsyncMock()) as mock_put:
            assert await echo(val) == val
            mock_put.assert_not_called()

        # 再次调用，缓存应失效，触发写入
        with cache.disabled():
            with patch.object(cache, "aget", side_effect=AsyncMock(return_value=None)) as mock_get:
                with patch.object(cache, "aput", side_effect=AsyncMock()) as mock_put:
                    result = await echo(val)
                    mock_get.assert_not_called()
                    mock_put.assert_not_called()
                    assert result == val

        # 离开上下文后，缓存应恢复正常
        with patch.object(cache, "aget", side_effect=AsyncMock(return_value=cache.serialize(val))) as mock_get:
            with patch.object(cache, "aput", side_effect=AsyncMock()) as mock_put:
                result = await echo(val)
                mock_get.assert_called_once()
                mock_put.assert_not_called()
                assert result == val
