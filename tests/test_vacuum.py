"""针对 ``vacuum`` / ``avacuum`` 的集成测试。

需要真实 Redis 服务器（字段 TTL 机制要求 Redis ≥ 7.4）。
按照设计说明（``docs/design/field-ttl-vacuum.md``）的测试计划，
用 ``HDEL`` / 删除整个 HASH 键来确定性地模拟字段过期，而非真实等待 TTL。
"""

from uuid import uuid4

import pytest
from redis import Redis
from redis.asyncio import Redis as AsyncRedis

from redis_func_cache import LruPolicy, RedisFuncCache
from redis_func_cache.policies.lru import LruMultiplePolicy
from redis_func_cache.policies.rr import RrPolicy

from ._catches import REDIS_URL

# 回归说明：vacuum 脚本曾对 RR 策略的 SET 索引执行 ZSCAN 而报 WRONGTYPE，
# RrPolicy 参数化覆盖该修复。
POLICY_FACTORIES = [(LruPolicy,), (LruMultiplePolicy,), (RrPolicy,)]


def _index_size(client, index_key) -> int:
    """索引结构（zset 或 set）的成员数（键缺失时为 0）。"""
    index_type = client.type(index_key)
    if isinstance(index_type, bytes):
        index_type = index_type.decode()
    return client.scard(index_key) if index_type == "set" else client.zcard(index_key)


async def _aindex_size(client, index_key) -> int:
    """``_index_size`` 的异步版本。"""
    index_type = await client.type(index_key)
    if isinstance(index_type, bytes):
        index_type = index_type.decode()
    if index_type == "set":
        return await client.scard(index_key)
    return await client.zcard(index_key)


def make_sync_cache(policy) -> RedisFuncCache:
    return RedisFuncCache(uuid4().hex, policy, factory=lambda: Redis.from_url(REDIS_URL))


def make_async_cache(policy) -> RedisFuncCache:
    return RedisFuncCache(uuid4().hex, policy, factory=lambda: AsyncRedis.from_url(REDIS_URL))


@pytest.mark.parametrize("policy_factory", POLICY_FACTORIES, ids=["single", "multiple", "rr"])
def test_vacuum_removes_ghosts(policy_factory):
    """字段全部过期后，vacuum 清除全部幽灵成员。"""
    cache = make_sync_cache(policy_factory[0])
    client = Redis.from_url(REDIS_URL)

    def echo(x):
        return x

    decorated = cache.decorate(ttl=600)(echo)
    values = [uuid4().hex for _ in range(3)]
    for v in values:
        assert decorated(v) == v

    index_key, hmap_key = cache.policy.calc_keys(echo)
    assert _index_size(client, index_key) == 3

    client.delete(hmap_key)  # 所有字段瞬间"过期"，全部成为幽灵
    assert cache.vacuum() == 3
    assert _index_size(client, index_key) == 0


def test_vacuum_keeps_live_entries():
    """只清除过期字段对应的成员，活条目不受影响。"""
    cache = make_sync_cache(LruPolicy)
    client = Redis.from_url(REDIS_URL)

    def echo(x):
        return x

    decorated = cache.decorate(ttl=600)(echo)
    assert decorated("a") == "a"
    assert decorated("b") == "b"

    zset_key, hmap_key = cache.policy.calc_keys(echo)
    hash_a = cache.policy.calc_hash(echo, ("a",), {})
    hash_b = cache.policy.calc_hash(echo, ("b",), {})
    client.hdel(hmap_key, hash_a)

    assert cache.vacuum() == 1
    assert client.zcard(zset_key) == 1
    assert client.hexists(hmap_key, hash_b)


def test_vacuum_on_empty_cache():
    """空缓存上 vacuum 返回 0，且不创建任何键。"""
    cache = make_sync_cache(LruPolicy)
    client = Redis.from_url(REDIS_URL)

    assert cache.vacuum() == 0
    zset_key, hmap_key = cache.policy.calc_keys()
    assert client.exists(zset_key, hmap_key) == 0


def test_vacuum_with_small_batch_size():
    """小 batch_size 时游标循环仍能清除全部幽灵。"""
    cache = make_sync_cache(LruPolicy)
    client = Redis.from_url(REDIS_URL)

    def echo(x):
        return x

    decorated = cache.decorate(ttl=600)(echo)
    count = 20
    for _ in range(count):
        assert decorated(uuid4().hex) is not None

    zset_key, hmap_key = cache.policy.calc_keys(echo)
    client.delete(hmap_key)

    assert cache.vacuum(batch_size=5) == count
    assert client.zcard(zset_key) == 0


def test_vacuum_guard_against_async_client():
    """同步 vacuum 遇到异步客户端时抛出 RuntimeError。"""
    cache = make_async_cache(LruPolicy)
    with pytest.raises(RuntimeError, match="synchronous"):
        cache.vacuum()


@pytest.mark.asyncio(loop_scope="function")
@pytest.mark.parametrize("policy_factory", POLICY_FACTORIES, ids=["single", "multiple", "rr"])
async def test_avacuum_removes_ghosts(policy_factory):
    """``avacuum`` 的异步镜像测试。"""
    cache = make_async_cache(policy_factory[0])
    client = AsyncRedis.from_url(REDIS_URL)

    async def echo(x):
        return x

    decorated = cache.decorate(ttl=600)(echo)
    values = [uuid4().hex for _ in range(3)]
    for v in values:
        assert await decorated(v) == v

    index_key, hmap_key = cache.policy.calc_keys(echo)
    assert await _aindex_size(client, index_key) == 3

    await client.delete(hmap_key)
    assert await cache.avacuum() == 3
    assert await _aindex_size(client, index_key) == 0


@pytest.mark.asyncio(loop_scope="function")
async def test_avacuum_guard_against_sync_client():
    """异步 avacuum 遇到同步客户端时抛出 RuntimeError。"""
    cache = make_sync_cache(LruPolicy)
    with pytest.raises(RuntimeError, match="asynchronous"):
        await cache.avacuum()


def test_multiple_policy_get_size():
    """多策略的 get_size 返回跨所有函数键对的条目总数。"""
    cache = make_sync_cache(LruMultiplePolicy)

    def echo_a(x):
        return x

    def echo_b(x):
        return x

    for v in ("a", "b", "c"):
        assert cache.decorate(ttl=600)(echo_a)(v) == v
    assert cache.decorate(ttl=600)(echo_b)("d") == "d"

    assert cache.policy.get_size(redis_client=cache.get_redis_client()) == 4


@pytest.mark.asyncio(loop_scope="function")
async def test_multiple_policy_aget_size():
    """``aget_size`` 的异步镜像测试。"""
    cache = make_async_cache(LruMultiplePolicy)

    async def echo_a(x):
        return x

    async def echo_b(x):
        return x

    for v in ("a", "b"):
        assert await cache.decorate(ttl=600)(echo_a)(v) == v
    assert await cache.decorate(ttl=600)(echo_b)("c") == "c"

    assert await cache.policy.aget_size(redis_client=cache.get_redis_client()) == 3
