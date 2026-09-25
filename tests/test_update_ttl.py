import time
from uuid import uuid4

import pytest

from redis_func_cache import RedisFuncCache
from redis_func_cache.policies.lru import LruPolicy
from redis_func_cache.policies.rr import RrPolicy

from ._catches import CACHES, redis_factory
from ._mocks import patch_object


@pytest.fixture(autouse=True)
def clean_caches():
    """自动清理缓存的夹具，在每个测试前后运行。"""
    # 测试前清理
    for cache in CACHES.values():
        cache.policy.purge(redis_client=cache.get_redis_client())
    yield
    # 测试后清理
    for cache in CACHES.values():
        cache.policy.purge(redis_client=cache.get_redis_client())


def test_update_ttl_default_behavior():
    """测试update_ttl默认行为（True）- 访问后应更新TTL"""
    for cache in CACHES.values():
        # 创建一个短TTL的缓存实例来测试
        short_ttl_cache = RedisFuncCache(
            __name__,
            type(cache.policy)(),
            factory=redis_factory,
            maxsize=cache.maxsize,
            ttl=2,  # 2秒TTL
        )
        short_ttl_cache.policy.purge(redis_client=short_ttl_cache.get_redis_client())

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
        with patch_object(short_ttl_cache, "put") as mock_put:
            result2 = echo(val)
            assert result2 == val
            # 在update_ttl=True模式下，缓存命中不应该触发重新存储
            mock_put.assert_not_called()

        # 再等待1.5秒（总共2.5秒，超过初始TTL）
        time.sleep(1.5)

        # 第三次调用，如果TTL被更新了，应该仍然命中缓存
        with patch_object(short_ttl_cache, "put") as mock_put:
            result3 = echo(val)
            assert result3 == val
            # 在update_ttl=True模式下，即使过了初始TTL，也应该命中缓存
            mock_put.assert_not_called()

        short_ttl_cache.policy.purge(redis_client=short_ttl_cache.get_redis_client())


def test_update_ttl_false_behavior():
    """测试update_ttl=False行为 - 访问后不应更新TTL"""
    for cache in CACHES.values():
        # 创建一个不更新TTL的缓存实例
        no_update_ttl_cache = RedisFuncCache(
            __name__,
            type(cache.policy)(),
            factory=redis_factory,
            maxsize=cache.maxsize,
            ttl=2,  # 2秒TTL
            update_ttl=False,  # 不更新TTL
        )
        no_update_ttl_cache.policy.purge(redis_client=no_update_ttl_cache.get_redis_client())

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
        with patch_object(no_update_ttl_cache, "put") as mock_put:
            result2 = echo(val)
            assert result2 == val
            # 在update_ttl=False模式下，缓存命中不应该触发重新存储
            mock_put.assert_not_called()

        # 再等待1.5秒（总共2.5秒，超过初始TTL）
        time.sleep(1.5)

        # 第三次调用，如果TTL没有被更新，应该触发重新计算
        with patch_object(no_update_ttl_cache, "put") as mock_put:
            result3 = echo(val)
            assert result3 == val
            # 在update_ttl=False模式下，过了初始TTL应该触发重新存储
            mock_put.assert_called_once()

        no_update_ttl_cache.policy.purge(redis_client=no_update_ttl_cache.get_redis_client())


def test_miss_does_not_slide_ttl():
    """get miss 不应滑动结构 TTL，只有命中才刷新（行为变更：one-item lazy vacuum 语义）。

    索引键与 hash 键使用较长 TTL（60 秒），通过数值断言而不是等待过期。
    """
    for cache in CACHES.values():
        ttl_cache = RedisFuncCache(
            __name__,
            type(cache.policy)(),
            factory=redis_factory,
            maxsize=cache.maxsize,
            ttl=60,
            update_ttl=True,
        )
        ttl_cache.policy.purge(redis_client=ttl_cache.get_redis_client())

        def echo(x):
            return x

        decorated = ttl_cache.decorate()(echo)
        client = ttl_cache.get_redis_client()
        index_key, hmap_key = ttl_cache.policy.calc_keys(echo)

        assert decorated("a") == "a"  # put：两侧 TTL 设为 60

        time.sleep(2)

        assert decorated("b") == "b"  # miss：不应把 TTL 重置回 60
        ttl_index = client.ttl(index_key)
        ttl_hash = client.ttl(hmap_key)
        assert 0 < ttl_index <= 58, f"miss 不应滑动 TTL，实际 {ttl_index}"
        assert 0 < ttl_hash <= 58, f"miss 不应滑动 TTL，实际 {ttl_hash}"

        time.sleep(1)

        assert decorated("a") == "a"  # hit：TTL 应重置回 ~60
        assert client.ttl(index_key) >= 58
        assert client.ttl(hmap_key) >= 58

        ttl_cache.policy.purge(redis_client=ttl_cache.get_redis_client())


def _index_size(client, policy, index_key) -> int:
    """索引结构（zset 或 set）的成员数。"""
    return client.scard(index_key) if isinstance(policy, RrPolicy) else client.zcard(index_key)


@pytest.mark.parametrize("policy", [LruPolicy(), RrPolicy()], ids=["lru", "rr"])
def test_miss_cleans_index_ghost(policy):
    """get miss 时做单条惰性清理：hash 字段"过期"后的索引幽灵成员被移除。

    patch 掉 put 以免清理后重新写入，从而能直接观察到清理效果。
    """
    cache = RedisFuncCache(__name__, policy, factory=redis_factory, maxsize=8)
    cache.policy.purge(redis_client=cache.get_redis_client())

    def echo(x):
        return x

    decorated = cache.decorate()(echo)
    client = cache.get_redis_client()
    index_key, hmap_key = cache.policy.calc_keys(echo)
    hash_a = cache.policy.calc_hash(echo, ("a",), {})

    assert decorated("a") == "a"
    client.hdel(hmap_key, hash_a)  # 模拟字段过期 → 索引幽灵
    assert _index_size(client, policy, index_key) == 1

    with patch_object(cache, "put"):  # put 被拦截，不回写
        assert decorated("a") == "a"  # miss：get 脚本清理幽灵

    assert _index_size(client, policy, index_key) == 0
    cache.policy.purge(redis_client=client)


@pytest.mark.parametrize("policy", [LruPolicy(), RrPolicy()], ids=["lru", "rr"])
def test_miss_cleans_orphan_hash_field(policy):
    """get miss 时做单条惰性清理：索引成员丢失后的孤儿 hash 字段被移除。"""
    cache = RedisFuncCache(__name__, policy, factory=redis_factory, maxsize=8)
    cache.policy.purge(redis_client=cache.get_redis_client())

    def echo(x):
        return x

    decorated = cache.decorate()(echo)
    client = cache.get_redis_client()
    index_key, hmap_key = cache.policy.calc_keys(echo)
    hash_a = cache.policy.calc_hash(echo, ("a",), {})

    assert decorated("a") == "a"
    if isinstance(policy, RrPolicy):
        client.srem(index_key, hash_a)
    else:
        client.zrem(index_key, hash_a)
    assert client.hlen(hmap_key) == 1

    with patch_object(cache, "put"):  # put 被拦截，不回写
        assert decorated("a") == "a"  # miss：get 脚本清理孤儿字段

    assert client.hlen(hmap_key) == 0
    cache.policy.purge(redis_client=client)
