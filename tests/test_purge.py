"""针对 ``purge`` / ``apurge`` 的集成测试。

需要真实 Redis 服务器。
按照设计说明（``docs/design/purge.md``）的测试计划：
单策略删除静态键对；多策略经 `SCAN` 枚举并分批 `UNLINK`，
验证删除的键数量准确、活缓存不可再命中。
"""

from uuid import uuid4

import pytest
from redis import Redis
from redis.asyncio import Redis as AsyncRedis
from redis.connection import ConnectionPool

from redis_func_cache import LruPolicy, RedisFuncCache
from redis_func_cache.policies.lru import LruMultiplePolicy

from ._catches import REDIS_URL

POLICY_FACTORIES = [(LruPolicy,), (LruMultiplePolicy,)]

SYNC_POOL = ConnectionPool.from_url(REDIS_URL)


def make_sync_cache(policy) -> RedisFuncCache:
    return RedisFuncCache(uuid4().hex, policy, factory=lambda: Redis(connection_pool=SYNC_POOL))


def make_async_cache(policy) -> RedisFuncCache:
    return RedisFuncCache(uuid4().hex, policy, factory=lambda: AsyncRedis.from_url(REDIS_URL))


def test_single_policy_purge():
    """单策略 purge 删除两个静态键，返回 2，之后重新计算。"""
    cache = make_sync_cache(LruPolicy)
    client = Redis.from_url(REDIS_URL)

    def echo(x):
        return x

    decorated = cache.decorate(echo)
    assert decorated("a") == "a"

    zset_key, hmap_key = cache.policy.calc_key_pair(echo)
    assert cache.purge() == 2
    assert client.exists(zset_key, hmap_key) == 0
    assert decorated("a") == "a"  # 缓存已清空，重新执行


def test_multiple_policy_purge():
    """多策略 purge 经 SCAN 枚举删除所有函数的键对，返回键数。"""
    cache = make_sync_cache(LruMultiplePolicy)
    client = Redis.from_url(REDIS_URL)

    def echo_a(x):
        return x

    def echo_b(x):
        return x

    cache.decorate(echo_a)("a")
    cache.decorate(echo_b)("b")

    assert cache.policy.purge(redis_client=cache.get_redis_client()) == 4  # 每个函数一个 ZSET + 一个 HASH
    pat = f"{cache.prefix}{cache.name}:*"
    assert list(client.scan_iter(match=pat)) == []


def test_multiple_policy_purge_with_small_batch_size():
    """batch_size=1 时分批 UNLINK 仍删除全部键，计数准确。"""
    cache = make_sync_cache(LruMultiplePolicy)
    client = Redis.from_url(REDIS_URL)

    def echo_a(x):
        return x

    def echo_b(x):
        return x

    cache.decorate(echo_a)("a")
    cache.decorate(echo_b)("b")

    assert cache.policy.purge(redis_client=cache.get_redis_client(), batch_size=1) == 4
    pat = f"{cache.prefix}{cache.name}:*"
    assert list(client.scan_iter(match=pat)) == []


def test_purge_on_empty_cache():
    """从未写入的缓存 purge 返回 0。"""
    cache = make_sync_cache(LruMultiplePolicy)
    assert cache.purge() == 0


def test_purge_guard_against_async_client():
    """同步 purge 遇到异步客户端时抛出 RuntimeError。"""
    cache = make_async_cache(LruPolicy)
    with pytest.raises(TypeError, match="synchronous"):
        cache.purge()


@pytest.mark.asyncio(loop_scope="function")
@pytest.mark.parametrize("policy_factory", POLICY_FACTORIES, ids=["single", "multiple"])
async def test_apurge(policy_factory):
    """``apurge`` 的异步镜像测试。"""
    cache = make_async_cache(policy_factory[0])
    client = AsyncRedis.from_url(REDIS_URL)

    async def echo(x):
        return x

    decorated = cache.decorate(echo)
    assert await decorated("a") == "a"

    assert await cache.apurge(batch_size=1) >= 2
    pat = f"{cache.prefix}{cache.name}:*"
    assert [key async for key in client.scan_iter(match=pat)] == []


@pytest.mark.asyncio(loop_scope="function")
async def test_apurge_guard_against_sync_client():
    """异步 apurge 遇到同步客户端时抛出 RuntimeError。"""
    cache = make_sync_cache(LruPolicy)
    with pytest.raises(TypeError, match="asynchronous"):
        await cache.apurge()
