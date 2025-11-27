import time
from unittest.mock import patch
from uuid import uuid4

import pytest

from redis_func_cache import RedisFuncCache

from ._catches import CACHES, redis_factory


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


def test_update_ttl_default_behavior():
    """测试update_ttl默认行为（True）- 访问后应更新TTL"""
    for cache in CACHES.values():
        # 创建一个短TTL的缓存实例来测试
        short_ttl_cache = RedisFuncCache(
            __name__,
            type(cache.policy)(),
            redis_factory=redis_factory,
            maxsize=cache.maxsize,
            ttl=2,  # 2秒TTL
        )
        short_ttl_cache.policy.purge()

        @short_ttl_cache
        def echo(x):
            return x

        val = uuid4().hex
        # 第一次调用，填充缓存
        result1 = echo(val)
        assert result1 == val

        # 等待1秒（TTL的一半时间）
        time.sleep(1)

        # 第二次调用，应该命中缓存并更新TTL
        with patch.object(short_ttl_cache, "put") as mock_put:
            result2 = echo(val)
            assert result2 == val
            # 在update_ttl=True模式下，缓存命中不应该触发重新存储
            mock_put.assert_not_called()

        # 再等待1.5秒（总共2.5秒，超过初始TTL）
        time.sleep(1.5)

        # 第三次调用，如果TTL被更新了，应该仍然命中缓存
        with patch.object(short_ttl_cache, "put") as mock_put:
            result3 = echo(val)
            assert result3 == val
            # 在update_ttl=True模式下，即使过了初始TTL，也应该命中缓存
            mock_put.assert_not_called()

        short_ttl_cache.policy.purge()


def test_update_ttl_false_behavior():
    """测试update_ttl=False行为 - 访问后不应更新TTL"""
    for cache in CACHES.values():
        # 创建一个不更新TTL的缓存实例
        no_update_ttl_cache = RedisFuncCache(
            __name__,
            type(cache.policy)(),
            redis_factory=redis_factory,
            maxsize=cache.maxsize,
            ttl=2,  # 2秒TTL
            update_ttl=False,  # 不更新TTL
        )
        no_update_ttl_cache.policy.purge()

        @no_update_ttl_cache
        def echo(x):
            return x

        val = uuid4().hex
        # 第一次调用，填充缓存
        result1 = echo(val)
        assert result1 == val

        # 等待1秒（TTL的一半时间）
        time.sleep(1)

        # 第二次调用，应该命中缓存但不更新TTL
        with patch.object(no_update_ttl_cache, "put") as mock_put:
            result2 = echo(val)
            assert result2 == val
            # 在update_ttl=False模式下，缓存命中不应该触发重新存储
            mock_put.assert_not_called()

        # 再等待1.5秒（总共2.5秒，超过初始TTL）
        time.sleep(1.5)

        # 第三次调用，如果TTL没有被更新，应该触发重新计算
        with patch.object(no_update_ttl_cache, "put") as mock_put:
            result3 = echo(val)
            assert result3 == val
            # 在update_ttl=False模式下，过了初始TTL应该触发重新存储
            mock_put.assert_called_once()

        no_update_ttl_cache.policy.purge()
