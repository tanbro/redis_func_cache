"""针对 ``vacuum`` / ``avacuum`` 的集成测试。

需要真实 Redis 服务器（字段 TTL 机制要求 Redis ≥ 7.4）。
按照设计说明（``docs/design/field-ttl-vacuum.md``）的测试计划，
用 ``HDEL`` / 删除整个 HASH 键来确定性地模拟字段过期，而非真实等待 TTL。
"""

import asyncio
import time
from uuid import uuid4

import pytest
from redis import Redis
from redis.asyncio import Redis as AsyncRedis
from redis.connection import ConnectionPool

from redis_func_cache import LruPolicy, RedisFuncCache
from redis_func_cache.policies.lru import LruMultiplePolicy
from redis_func_cache.policies.rr import RrPolicy

from ._catches import REDIS_URL, async_redis_pool_factory
from ._mocks import patch_object

# 回归说明：vacuum 脚本曾对 RR 策略的 SET 索引执行 ZSCAN 而报 WRONGTYPE，
# RrPolicy 参数化覆盖该修复。
POLICY_FACTORIES = [(LruPolicy,), (LruMultiplePolicy,), (RrPolicy,)]

SYNC_POOL = ConnectionPool.from_url(REDIS_URL)


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
    return RedisFuncCache(uuid4().hex, policy, factory=lambda: Redis(connection_pool=SYNC_POOL))


def make_async_cache(policy) -> RedisFuncCache:
    return RedisFuncCache(uuid4().hex, policy, factory=async_redis_pool_factory)


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

    index_key, hmap_key = cache.policy.calc_key_pair(echo)
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

    zset_key, hmap_key = cache.policy.calc_key_pair(echo)
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
    zset_key, hmap_key = cache.policy.calc_key_pair()
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

    zset_key, hmap_key = cache.policy.calc_key_pair(echo)
    client.delete(hmap_key)

    assert cache.vacuum(batch_size=5) == count
    assert client.zcard(zset_key) == 0


def test_vacuum_guard_against_async_client():
    """同步 vacuum 遇到异步客户端时抛出 TypeError。"""
    cache = make_async_cache(LruPolicy)
    with pytest.raises(TypeError, match="synchronous"):
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

    index_key, hmap_key = cache.policy.calc_key_pair(echo)
    assert await _aindex_size(client, index_key) == 3

    await client.delete(hmap_key)
    assert await cache.avacuum() == 3
    assert await _aindex_size(client, index_key) == 0


@pytest.mark.asyncio(loop_scope="function")
async def test_avacuum_guard_against_sync_client():
    """异步 avacuum 遇到同步客户端时抛出 TypeError。"""
    cache = make_sync_cache(LruPolicy)
    with pytest.raises(TypeError, match="asynchronous"):
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


# ---------------------------------------------------------------------------
# 真实字段过期端到端：不模拟 HDEL，让 HEXPIRE 自然到期，验证
# "字段过期 → 索引幽灵 → 清理" 的完整链路（miss 单条惰性清理 / vacuum 批量清理）。
# ---------------------------------------------------------------------------

REAL_TTL = 1  # 字段 TTL（秒），最小可等待值
EXPIRY_WAIT = 1.6  # 覆盖 TTL 到期 + 脚本执行间隔


@pytest.mark.parametrize("policy", [LruPolicy, RrPolicy], ids=["lru", "rr"])
def test_field_ttl_expiry_lazy_cleanup_on_miss(policy):
    """真实 HEXPIRE 到期后，get miss 的单条惰性清理逐个移除索引幽灵。"""
    cache = make_sync_cache(policy)

    def echo(x):
        return x

    decorated = cache.decorate(ttl=REAL_TTL)(echo)
    client = cache.get_redis_client()
    index_key, hmap_key = cache.policy.calc_key_pair(echo)

    assert decorated("a") == "a"
    assert decorated("b") == "b"
    assert _index_size(client, index_key) == 2

    time.sleep(EXPIRY_WAIT)  # 两个字段的 HEXPIRE 自然到期

    # 幽灵仍在索引中（get_size 计入），hash 字段已被 Redis 判定过期
    assert _index_size(client, index_key) == 2

    with patch_object(cache, "put"):  # put 被拦截，不回写，以便观察清理
        assert decorated("a") == "a"  # miss：惰性清理移除幽灵 a
        assert _index_size(client, index_key) == 1
        assert decorated("b") == "b"  # miss：惰性清理移除幽灵 b
        assert _index_size(client, index_key) == 0
        assert client.hlen(hmap_key) == 0

    cache.policy.purge(redis_client=client)


@pytest.mark.parametrize("policy", [LruPolicy, RrPolicy], ids=["lru", "rr"])
def test_field_ttl_expiry_vacuum_collects(policy):
    """真实 HEXPIRE 到期后，vacuum 一次性收走全部幽灵，get 随后重算。"""
    cache = make_sync_cache(policy)

    def echo(x):
        return x

    decorated = cache.decorate(ttl=REAL_TTL)(echo)
    client = cache.get_redis_client()
    index_key, hmap_key = cache.policy.calc_key_pair(echo)

    for v in ("a", "b", "c"):
        assert decorated(v) == v
    assert _index_size(client, index_key) == 3

    time.sleep(EXPIRY_WAIT)

    assert cache.vacuum() == 3
    assert _index_size(client, index_key) == 0
    assert client.hlen(hmap_key) == 0

    # vacuum 之后 get 重算并回写
    assert decorated("a") == "a"
    assert _index_size(client, index_key) == 1
    assert client.hlen(hmap_key) == 1

    cache.policy.purge(redis_client=client)


@pytest.mark.asyncio(loop_scope="function")
@pytest.mark.parametrize("policy", [LruPolicy, RrPolicy], ids=["lru", "rr"])
async def test_async_field_ttl_expiry_lazy_cleanup_on_miss(policy):
    """真实字段过期 + 异步 miss 惰性清理。"""
    cache = make_async_cache(policy)

    async def echo(x):
        return x

    decorated = cache.decorate(ttl=REAL_TTL)(echo)
    client = cache.get_redis_client()
    index_key, hmap_key = cache.policy.calc_key_pair(echo)

    assert await decorated("a") == "a"
    assert await decorated("b") == "b"
    assert await _aindex_size(client, index_key) == 2

    await asyncio.sleep(EXPIRY_WAIT)

    assert await _aindex_size(client, index_key) == 2

    with patch_object(cache, "aput"):
        assert await decorated("a") == "a"
        assert await _aindex_size(client, index_key) == 1
        assert await decorated("b") == "b"
        assert await _aindex_size(client, index_key) == 0
        assert await client.hlen(hmap_key) == 0

    await cache.policy.apurge(redis_client=client)


@pytest.mark.asyncio(loop_scope="function")
@pytest.mark.parametrize("policy", [LruPolicy, RrPolicy], ids=["lru", "rr"])
async def test_async_field_ttl_expiry_vacuum_collects(policy):
    """真实字段过期 + ``avacuum`` 批量清理。"""
    cache = make_async_cache(policy)

    async def echo(x):
        return x

    decorated = cache.decorate(ttl=REAL_TTL)(echo)
    client = cache.get_redis_client()
    index_key, _ = cache.policy.calc_key_pair(echo)

    for v in ("a", "b", "c"):
        assert await decorated(v) == v
    assert await _aindex_size(client, index_key) == 3

    await asyncio.sleep(EXPIRY_WAIT)

    assert await cache.avacuum() == 3
    assert await _aindex_size(client, index_key) == 0

    assert await decorated("a") == "a"
    assert await _aindex_size(client, index_key) == 1

    await cache.policy.apurge(redis_client=client)
