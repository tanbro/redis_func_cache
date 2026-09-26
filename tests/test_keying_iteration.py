"""``iterate_key_pairs`` / ``aiterate_key_pairs`` 的集成测试。

单策略应产出静态键对；多策略经 ``SCAN`` 流式枚举每个函数的键对。
集群变体依赖 ``REDIS_CLUSTER_NODES`` 环境变量（docker/redis.compose.yaml）。
"""

from uuid import uuid4

import pytest
from redis import Redis
from redis.asyncio import Redis as AsyncRedis
from redis.asyncio.cluster import RedisCluster as AsyncRedisCluster

from redis_func_cache import LruPolicy, RedisFuncCache
from redis_func_cache.policies.fifo import FifoClusterMultiplePolicy, FifoClusterPolicy
from redis_func_cache.policies.lru import LruClusterMultiplePolicy, LruClusterPolicy, LruMultiplePolicy
from redis_func_cache.policies.rr import RrClusterMultiplePolicy, RrClusterPolicy

from ._catches import (
    ASYNC_CACHES,
    ASYNC_CLUSTER_NODES,
    ASYNC_MULTI_CACHES,
    CLUSTER_CACHES,
    CLUSTER_MULTI_CACHES,
    REDIS_CLUSTER_NODES,
    REDIS_URL,
)


def make_sync_cache(policy) -> RedisFuncCache:
    return RedisFuncCache(uuid4().hex, policy, factory=lambda: Redis.from_url(REDIS_URL))


def make_async_cache(policy) -> RedisFuncCache:
    return RedisFuncCache(uuid4().hex, policy, factory=lambda: AsyncRedis.from_url(REDIS_URL))


def make_async_cluster_cache(policy) -> RedisFuncCache:
    return RedisFuncCache(
        uuid4().hex,
        policy,
        factory=lambda: AsyncRedisCluster(startup_nodes=ASYNC_CLUSTER_NODES),  # type: ignore[abstract]
    )


def _norm(key) -> str:
    return key.decode() if isinstance(key, bytes) else key


def _norm_pair(pair) -> tuple[str, str]:
    k, v = pair
    return _norm(k), _norm(v)


def test_single_iterate_key_pairs():
    """单策略 iterate 返回唯一的静态键对，且与 calc_key_pair 一致。"""
    cache = make_sync_cache(LruPolicy)

    def echo(x):
        return x

    cache.decorate(echo)("a")

    pairs = {_norm_pair(p) for p in cache.policy.iterate_key_pairs(cache.get_redis_client())}
    assert pairs == {_norm_pair(cache.policy.calc_key_pair(echo))}


def test_multiple_iterate_key_pairs():
    """多策略 iterate 经 SCAN 产出每个函数一个键对。"""

    def echo_a(x):
        return x

    def echo_b(x):
        return x

    cache = make_sync_cache(LruMultiplePolicy)
    cache.decorate(echo_a)("a")
    cache.decorate(echo_b)("b")

    pairs = {_norm(k) for k, _ in cache.policy.iterate_key_pairs(cache.get_redis_client())}
    assert pairs == {
        cache.policy.calc_key_pair(echo_a)[0],
        cache.policy.calc_key_pair(echo_b)[0],
    }

    # purge 之后不再枚举到任何键对
    cache.policy.purge(cache.get_redis_client())
    assert list(cache.policy.iterate_key_pairs(cache.get_redis_client())) == []


def test_iterate_key_pairs_accept_any_client_type():
    """keying 层不做运行时 guard（静态窄类型负责）；基类实现不触碰客户端。"""
    cache = make_sync_cache(LruPolicy)
    # 同步客户端走同步 iterate 正常返回
    assert list(cache.policy.iterate_key_pairs(cache.get_redis_client()))


@pytest.mark.asyncio(loop_scope="function")
async def test_single_aiterate_key_pairs():
    """单策略 aiterate 的异步镜像测试。"""
    cache = make_async_cache(LruPolicy)

    async def echo(x):
        return x

    await cache.decorate(echo)("a")

    pairs = {_norm_pair(p) for p in cache.policy.iterate_key_pairs(cache.get_redis_client())}
    assert pairs == {_norm_pair(cache.policy.calc_key_pair(echo))}


@pytest.mark.asyncio(loop_scope="function")
async def test_multiple_aiterate_key_pairs():
    """多策略 aiterate 的异步镜像测试。"""

    async def echo_a(x):
        return x

    async def echo_b(x):
        return x

    cache = make_async_cache(LruMultiplePolicy)
    await cache.decorate(echo_a)("a")
    await cache.decorate(echo_b)("b")

    pairs = {_norm(k) async for k, _ in cache.policy.aiterate_key_pairs(cache.get_redis_client())}
    assert pairs == {
        cache.policy.calc_key_pair(echo_a)[0],
        cache.policy.calc_key_pair(echo_b)[0],
    }

    await cache.policy.apurge(cache.get_redis_client())
    assert [p async for p in cache.policy.aiterate_key_pairs(cache.get_redis_client())] == []


@pytest.mark.parametrize("cache_name", ["lru", "rr"])
def test_cluster_iterate_key_pairs(cache_name):
    """集群单策略的 iterate 在真实集群上产出静态键对。"""
    cache = CLUSTER_CACHES[cache_name]

    def echo(x):
        return x

    cache.decorate(echo)("a")
    try:
        pairs = {_norm_pair(p) for p in cache.policy.iterate_key_pairs(cache.get_redis_client())}
        assert pairs == {_norm_pair(cache.policy.calc_key_pair(echo))}
    finally:
        cache.policy.purge(cache.get_redis_client())


@pytest.mark.parametrize("cache_name", ["lru", "rr"])
def test_cluster_multiple_iterate_key_pairs(cache_name):
    """集群多策略的 iterate 在真实集群上产出每个函数一个键对。"""
    cache = CLUSTER_MULTI_CACHES[cache_name]

    def echo_a(x):
        return x

    def echo_b(x):
        return x

    cache.decorate(echo_a)("a")
    cache.decorate(echo_b)("b")
    try:
        pairs = {_norm(k) for k, _ in cache.policy.iterate_key_pairs(cache.get_redis_client())}
        assert pairs == {
            cache.policy.calc_key_pair(echo_a)[0],
            cache.policy.calc_key_pair(echo_b)[0],
        }
    finally:
        cache.policy.purge(cache.get_redis_client())


@pytest.mark.asyncio(loop_scope="function")
async def test_async_single_aget_size_and_aiterate():
    """异步单策略缓存：aget_size 与 maxsize 一致，aiterate 产出静态键对。"""
    for cache in ASYNC_CACHES.values():

        @cache
        async def echo(x):
            return x

        for i in range(3):
            assert i == await echo(i)

        assert await cache.policy.aget_size(cache.get_redis_client()) == 3
        pairs = {_norm_pair(p) async for p in cache.policy.aiterate_key_pairs(cache.get_redis_client())}
        assert pairs == {_norm_pair(cache.policy.calc_key_pair(echo))}


@pytest.mark.asyncio(loop_scope="function")
async def test_async_multiple_aget_size_and_aiterate():
    """异步多策略缓存：aget_size 为各函数条目之和，aiterate 产出全部键对。"""
    for cache in ASYNC_MULTI_CACHES.values():

        async def echo_a(x):
            return x

        async def echo_b(x):
            return x

        for i in range(3):
            assert i == await cache.decorate(echo_a)(i)
            assert i == await cache.decorate(echo_b)(i)

        assert await cache.policy.aget_size(cache.get_redis_client()) == 6
        pairs = {_norm(k) async for k, _ in cache.policy.aiterate_key_pairs(cache.get_redis_client())}
        assert pairs == {
            cache.policy.calc_key_pair(echo_a)[0],
            cache.policy.calc_key_pair(echo_b)[0],
        }


@pytest.mark.asyncio(loop_scope="function")
@pytest.mark.skipif(not REDIS_CLUSTER_NODES, reason="REDIS_CLUSTER_NODES environment variable is not set")
@pytest.mark.parametrize("policy", [LruClusterPolicy, RrClusterPolicy, FifoClusterPolicy], ids=["lru", "rr", "fifo"])
async def test_async_cluster_single_keying(policy):
    """异步集群单策略：写入、aget_size、aiterate 全链路。"""
    cache = make_async_cluster_cache(policy)

    async def echo(x):
        return x

    cached_echo = cache.decorate(echo)
    assert await cached_echo("a") == "a"
    for i in range(3):
        assert i == await cached_echo(i)

    assert await cache.policy.aget_size(cache.get_redis_client()) == 4
    pairs = {_norm_pair(p) async for p in cache.policy.aiterate_key_pairs(cache.get_redis_client())}
    assert pairs == {_norm_pair(cache.policy.calc_key_pair(echo))}

    assert await cache.policy.apurge(cache.get_redis_client()) == 2
    assert await cache.policy.aget_size(cache.get_redis_client()) == 0


@pytest.mark.asyncio(loop_scope="function")
@pytest.mark.skipif(not REDIS_CLUSTER_NODES, reason="REDIS_CLUSTER_NODES environment variable is not set")
@pytest.mark.parametrize(
    "policy", [LruClusterMultiplePolicy, RrClusterMultiplePolicy, FifoClusterMultiplePolicy], ids=["lru", "rr", "fifo"]
)
async def test_async_cluster_multiple_keying(policy):
    """异步集群多策略：写入、aget_size、aiterate、apurge 全链路。"""
    cache = make_async_cluster_cache(policy)

    async def echo_a(x):
        return x

    async def echo_b(x):
        return x

    for i in range(3):
        assert i == await cache.decorate(echo_a)(i)
        assert i == await cache.decorate(echo_b)(i)

    assert await cache.policy.aget_size(cache.get_redis_client()) == 6

    pairs = {_norm(k) async for k, _ in cache.policy.aiterate_key_pairs(cache.get_redis_client())}
    assert pairs == {
        cache.policy.calc_key_pair(echo_a)[0],
        cache.policy.calc_key_pair(echo_b)[0],
    }

    assert await cache.policy.apurge(cache.get_redis_client()) == 4
    assert await cache.policy.aget_size(cache.get_redis_client()) == 0
