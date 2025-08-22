from unittest.mock import patch
from uuid import uuid4

import pytest

from redis_func_cache import RedisFuncCache

from ._catches import CACHES


@pytest.fixture(autouse=True)
def clean_caches():
    """自动清理缓存的夹具，在每个测试前后运行。"""
    # 测试前清理
    for cache in CACHES.values():
        cache.policy.purge()
    yield
    # 测试后清理
    for cache in CACHES.values():
        cache.policy.purge()


@pytest.mark.parametrize("cache_name,cache", CACHES.items())
def test_cache_disabled(cache_name, cache):
    """测试在 disabled 上下文中缓存是否被禁用。"""

    @cache
    def echo(x):
        return x

    val = uuid4().hex
    # 正常调用，缓存应生效
    assert echo(val) == val
    with patch.object(cache, "put") as mock_put:
        assert echo(val) == val
        mock_put.assert_not_called()

    # 在 disabled 上下文中调用，缓存应失效
    with cache.disabled():
        # 直接调用函数，不经过缓存
        with patch.object(cache, "get") as mock_get:
            with patch.object(cache, "put") as mock_put:
                # 模拟缓存未命中时的返回值
                mock_get.return_value = None
                result = echo(val)  # 不触发缓存写入
                # 确保 get 未被调用
                mock_get.assert_not_called()
                # 确保 put 未被调用
                mock_put.assert_not_called()
                # 确保返回值正确
                assert result == val

    # 离开上下文后，缓存应恢复正常
    with patch.object(cache, "get", return_value=cache.serialize(val)) as mock_get:
        with patch.object(cache, "put") as mock_put:
            result = echo(val)
            mock_get.assert_called_once()
            mock_put.assert_not_called()
            assert result == val


@pytest.mark.parametrize("cache_name,cache", CACHES.items())
def test_cache_put_only(cache_name, cache):
    """测试在 put_only 上下文中缓存行为。"""

    @cache
    def echo(x):
        return x

    val = uuid4().hex
    # 正常调用，缓存应生效
    assert echo(val) == val

    # 在 put_only 上下文中调用
    with cache.put_only():
        # 函数应该被执行，结果应该被写入缓存
        with patch.object(cache, "get") as mock_get:
            with patch.object(cache, "put") as mock_put:
                result = echo(val)
                # 确保 get 未被调用
                mock_get.assert_not_called()
                # 确保 put 被调用
                mock_put.assert_called_once()
                # 确保返回值正确
                assert result == val

    # 离开上下文后，缓存应恢复正常
    with patch.object(cache, "get", return_value=cache.serialize(val)) as mock_get:
        with patch.object(cache, "put") as mock_put:
            result = echo(val)
            mock_get.assert_called_once()
            mock_put.assert_not_called()
            assert result == val


@pytest.mark.parametrize("cache_name,cache", CACHES.items())
def test_cache_get_only(cache_name, cache):
    """测试在 get_only 上下文中缓存行为。"""

    @cache
    def echo(x):
        return x

    val = uuid4().hex
    # 正常调用，缓存应生效
    assert echo(val) == val

    # 在 get_only 上下文中调用
    with cache.get_only():
        # 函数不应该被执行，只应该从缓存中获取
        with patch.object(cache, "get", return_value=cache.serialize(val)) as mock_get:
            with patch.object(cache, "put") as mock_put:
                result = echo(val)
                # 确保 get 被调用
                mock_get.assert_called_once()
                # 确保 put 未被调用
                mock_put.assert_not_called()
                # 确保返回值正确
                assert result == val

    # 离开上下文后，缓存应恢复正常
    with patch.object(cache, "get", return_value=cache.serialize(val)) as mock_get:
        with patch.object(cache, "put") as mock_put:
            result = echo(val)
            mock_get.assert_called_once()
            mock_put.assert_not_called()
            assert result == val


@pytest.mark.parametrize("cache_name,cache", CACHES.items())
def test_cache_mode_enum(cache_name, cache):
    """测试使用 cache_mode 上下文管理器直接设置模式。"""

    @cache
    def echo(x):
        return x

    val = uuid4().hex
    # 正常调用，缓存应生效
    assert echo(val) == val

    # 使用 cache_mode 设置 DISABLED 模式
    with cache.cache_mode(RedisFuncCache.Mode.DISABLED):
        with patch.object(cache, "get") as mock_get:
            with patch.object(cache, "put") as mock_put:
                result = echo(val)
                mock_get.assert_not_called()
                mock_put.assert_not_called()
                assert result == val

    # 使用 cache_mode 设置 PUT_ONLY 模式
    with cache.cache_mode(RedisFuncCache.Mode.PUT_ONLY):
        with patch.object(cache, "get") as mock_get:
            with patch.object(cache, "put") as mock_put:
                result = echo(val)
                mock_get.assert_not_called()
                mock_put.assert_called_once()
                assert result == val

    # 使用 cache_mode 设置 GET_ONLY 模式
    with cache.cache_mode(RedisFuncCache.Mode.GET_ONLY):
        with patch.object(cache, "get", return_value=cache.serialize(val)) as mock_get:
            with patch.object(cache, "put") as mock_put:
                result = echo(val)
                mock_get.assert_called_once()
                mock_put.assert_not_called()
                assert result == val
