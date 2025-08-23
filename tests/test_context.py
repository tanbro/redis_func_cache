from unittest.mock import patch
from uuid import uuid4

import pytest

from redis_func_cache.cache import RedisFuncCache

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
def test_disable_rw(cache_name: str, cache: RedisFuncCache):  # noqa: F821
    """测试 disable_rw 上下文管理器是否正确禁用读写操作。"""

    @cache
    def echo(x):
        return x

    val = uuid4().hex
    # 正常调用，缓存应生效
    assert echo(val) == val
    with patch.object(cache, "put") as mock_put:
        assert cache.get_mode().read
        assert cache.get_mode().write
        assert echo(val) == val
        mock_put.assert_not_called()

    # 在 disable_rw 上下文中调用，缓存应完全禁用
    with cache.disable_rw():
        assert not cache.get_mode().read
        assert not cache.get_mode().write
        # 直接调用函数，不经过缓存
        with patch.object(cache, "get") as mock_get:
            with patch.object(cache, "put") as mock_put:
                # 模拟缓存未命中时的返回值
                mock_get.return_value = None
                result = echo(val)  # 不触发缓存读写
                # 确保 get 未被调用
                mock_get.assert_not_called()
                # 确保 put 未被调用
                mock_put.assert_not_called()
                # 确保返回值正确
                assert result == val

    # 离开上下文后，缓存应恢复正常
    assert cache.get_mode().read
    assert cache.get_mode().write
    with patch.object(cache, "get", return_value=cache.serialize(val)) as mock_get:
        with patch.object(cache, "put") as mock_put:
            result = echo(val)
            mock_get.assert_called_once()
            mock_put.assert_not_called()
            assert result == val


@pytest.mark.parametrize("cache_name,cache", CACHES.items())
def test_read_only(cache_name, cache):
    """测试 read_only 上下文管理器是否只允许读取操作。"""

    @cache
    def echo(x):
        return x

    val = uuid4().hex
    # 先正常调用一次，确保缓存中有值
    assert echo(val) == val

    # 在 read_only 上下文中调用
    with cache.read_only():
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


@pytest.mark.parametrize("cache_name,cache", CACHES.items())
def test_write_only(cache_name, cache):
    """测试 write_only 上下文管理器是否只允许写入操作。"""

    @cache
    def echo(x):
        return x

    val = uuid4().hex
    # 确保缓存中没有值
    cache.policy.purge()

    # 在 write_only 上下文中调用
    with cache.write_only():
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
