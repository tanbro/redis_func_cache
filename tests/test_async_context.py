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
            if aclose := getattr(client, "aclose", None):
                loop.run_until_complete(aclose)
            else:
                loop.run_until_complete(client.close())
    except Exception:
        pass


@pytest.fixture
def cache(async_redis_client):
    """创建独立的缓存实例"""
    cache_instance = RedisFuncCache(__name__, LruTPolicy(), factory=lambda: async_redis_client, maxsize=8)
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
    async def test_disable_rw(self, cache):
        """测试 disable_rw 上下文管理器是否正确禁用读写操作。"""

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

        # 在 disable_rw 上下文中调用，缓存应完全禁用
        with cache.disable_rw():
            # 直接调用函数，不经过缓存
            with patch.object(cache, "aget", side_effect=AsyncMock(return_value=None)) as mock_get:
                with patch.object(cache, "aput", side_effect=AsyncMock()) as mock_put:
                    result = await echo(val)  # 不触发缓存读写
                    # 确保 get 未被调用
                    mock_get.assert_not_called()
                    # 确保 put 未被调用
                    mock_put.assert_not_called()
                    # 确保返回值正确
                    assert result == val

        # 离开上下文后，缓存应恢复正常
        with patch.object(cache, "aget", side_effect=AsyncMock(return_value=cache.serialize(val))) as mock_get:
            with patch.object(cache, "aput", side_effect=AsyncMock()) as mock_put:
                result = await echo(val)
                mock_get.assert_called_once()
                mock_put.assert_not_called()
                assert result == val

    @pytest.mark.asyncio
    async def test_read_only(self, cache):
        """测试 read_only 上下文管理器是否只允许读取操作。"""

        @cache
        async def echo(x):
            await asyncio.sleep(0)
            return x

        val = uuid4().hex
        # 先正常调用一次，确保缓存中有值
        assert await echo(val) == val

        # 在 read_only 上下文中调用
        with cache.read_only():
            # 函数不应该被执行，只应该从缓存中获取
            with patch.object(cache, "aget", side_effect=AsyncMock(return_value=cache.serialize(val))) as mock_get:
                with patch.object(cache, "aput", side_effect=AsyncMock()) as mock_put:
                    result = await echo(val)
                    # 确保 get 被调用
                    mock_get.assert_called_once()
                    # 确保 put 未被调用
                    mock_put.assert_not_called()
                    # 确保返回值正确
                    assert result == val

    @pytest.mark.asyncio
    async def test_write_only(self, cache):
        """测试 write_only 上下文管理器是否只允许写入操作。"""

        @cache
        async def echo(x):
            await asyncio.sleep(0)
            return x

        val = uuid4().hex
        # 确保缓存中没有值
        await cache.policy.apurge()

        # 在 write_only 上下文中调用
        with cache.write_only():
            # 函数应该被执行，结果应该被写入缓存
            with patch.object(cache, "aget", side_effect=AsyncMock(return_value=None)) as mock_get:
                with patch.object(cache, "aput", side_effect=AsyncMock()) as mock_put:
                    result = await echo(val)
                    # 确保 get 未被调用
                    mock_get.assert_not_called()
                    # 确保 put 被调用
                    mock_put.assert_called_once()
                    # 确保返回值正确
                    assert result == val

        # 离开上下文后，缓存应恢复正常
        with patch.object(cache, "aget", side_effect=AsyncMock(return_value=cache.serialize(val))) as mock_get:
            with patch.object(cache, "aput", side_effect=AsyncMock()) as mock_put:
                result = await echo(val)
                mock_get.assert_called_once()
                mock_put.assert_not_called()
                assert result == val

    @pytest.mark.asyncio
    async def test_mode_cross_coroutine(self, cache):
        """测试 mode 在跨 coroutine 环境中的隔离性。"""
        from asyncio import create_task

        @cache
        async def echo(x):
            await asyncio.sleep(0)
            return x

        results = {}

        async def coroutine_func():
            # 在子协程中，mode 应该是默认值（可读可写可执行）
            mode = cache.get_mode()
            results["initial_mode"] = (mode.read, mode.write, mode.exec)

            # 在子协程中修改 mode
            with cache.disable_rw():
                mode = cache.get_mode()
                results["disabled_mode"] = (mode.read, mode.write, mode.exec)

            # 离开上下文后，mode 应该恢复为默认值
            mode = cache.get_mode()
            results["restored_mode"] = (mode.read, mode.write, mode.exec)

        # 主线程中的 mode 测试
        main_initial_mode = cache.get_mode()

        # 启动子协程
        task = create_task(coroutine_func())
        await task

        # 验证子协程中的 mode 隔离性
        assert results["initial_mode"] == (True, True, True)
        assert results["disabled_mode"] == (False, False, True)  # read=False, write=False, exec=True
        assert results["restored_mode"] == (True, True, True)

        # 主线程中的 mode 测试
        main_after_coroutine_mode = cache.get_mode()

        # 验证主线程中的 mode 未受影响
        assert (main_initial_mode.read, main_initial_mode.write, main_initial_mode.exec) == (True, True, True)
        assert (main_after_coroutine_mode.read, main_after_coroutine_mode.write, main_after_coroutine_mode.exec) == (
            True,
            True,
            True,
        )
