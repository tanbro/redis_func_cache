"""TTL / update_ttl / excludes / serializer 的异步镜像测试。

同步版本见 test_ttl.py、test_update_ttl.py、test_excludes.py、test_pickle.py；
本文件验证这些特性在 ``aget`` / ``aput`` 异步路径上的行为一致。
"""

import asyncio
import pickle
from copy import copy
from uuid import uuid4

import pytest
import pytest_asyncio

from redis_func_cache import RedisFuncCache
from redis_func_cache.policies.lru import LruPolicy
from redis_func_cache.policies.rr import RrPolicy

from ._catches import ASYNC_CACHES, async_redis_pool_factory
from ._mocks import patch_object

TTL_VALUES = [2, 3, 5]


@pytest_asyncio.fixture(autouse=True)
async def clean_async_caches():
    """自动清理异步缓存的夹具，在每个测试前后运行。"""
    coros = (cache.policy.apurge(cache.get_redis_client()) for cache in ASYNC_CACHES.values())
    await asyncio.gather(*coros)
    yield
    try:
        coros = (cache.policy.apurge(cache.get_redis_client()) for cache in ASYNC_CACHES.values())
        await asyncio.gather(*coros)
    except RuntimeError:
        pass


@pytest.mark.asyncio(loop_scope="function")
async def test_async_cache_ttl():
    """异步镜像 test_cache_ttl：各 TTL 独立过期，过期后触发重算。"""
    decorated = {}
    vals = {}
    for cache in ASYNC_CACHES.values():
        cid = id(cache)
        for i, ttl in enumerate(TTL_VALUES, start=1):

            def make_echo(cache=cache, ttl=ttl):
                @cache(ttl=ttl)
                async def echo(x):
                    return x

                return echo

            decorated[(cid, i)] = make_echo()
            vals[(cid, i)] = uuid4().hex

    # 填充缓存
    for key, fn in decorated.items():
        assert await fn(vals[key]) == vals[key]

    # 超过最小 TTL 后：ttl=2 的条目应已过期并重算
    await asyncio.sleep(min(TTL_VALUES) + 1)
    for cache in ASYNC_CACHES.values():
        cid = id(cache)
        with patch_object(cache, "aput") as mock_put:
            assert await decorated[(cid, 1)](vals[(cid, 1)]) == vals[(cid, 1)]
            mock_put.assert_called_once()

    # 超过所有 TTL 后：全部过期重算
    await asyncio.sleep(max(TTL_VALUES) + 1)
    for cache in ASYNC_CACHES.values():
        cid = id(cache)
        for i in (1, 2, 3):
            with patch_object(cache, "aput") as mock_put:
                assert await decorated[(cid, i)](vals[(cid, i)]) == vals[(cid, i)]
                mock_put.assert_called_once()


@pytest.mark.asyncio(loop_scope="function")
@pytest.mark.parametrize("policy", [LruPolicy, RrPolicy], ids=["lru", "rr"])
async def test_async_update_ttl_true(policy):
    """update_ttl=True（默认）：命中刷新 TTL，超过初始 TTL 仍命中。"""
    cache = RedisFuncCache(uuid4().hex, copy(policy), factory=async_redis_pool_factory, maxsize=8, ttl=2)
    await cache.policy.apurge(cache.get_redis_client())

    @cache
    async def echo(x):
        return x

    val = uuid4().hex
    assert await echo(val) == val  # 填充

    await asyncio.sleep(1)
    with patch_object(cache, "aput") as mock_put:
        assert await echo(val) == val
        mock_put.assert_not_called()

    await asyncio.sleep(1.5)  # 超过初始 TTL（2 秒）
    with patch_object(cache, "aput") as mock_put:
        assert await echo(val) == val  # 命中时已刷新 TTL，仍应命中
        mock_put.assert_not_called()

    await cache.policy.apurge(cache.get_redis_client())


@pytest.mark.asyncio(loop_scope="function")
@pytest.mark.parametrize("policy", [LruPolicy, RrPolicy], ids=["lru", "rr"])
async def test_async_update_ttl_false(policy):
    """update_ttl=False：命中不刷新 TTL，超过初始 TTL 后触发重算。"""
    cache = RedisFuncCache(
        uuid4().hex, copy(policy), factory=async_redis_pool_factory, maxsize=8, ttl=2, update_ttl=False
    )
    await cache.policy.apurge(cache.get_redis_client())

    @cache
    async def echo(x):
        return x

    val = uuid4().hex
    assert await echo(val) == val

    await asyncio.sleep(1)
    with patch_object(cache, "aput") as mock_put:
        assert await echo(val) == val
        mock_put.assert_not_called()

    await asyncio.sleep(1.5)
    with patch_object(cache, "aput") as mock_put:
        assert await echo(val) == val
        mock_put.assert_called_once()  # TTL 未刷新，已过期重算

    await cache.policy.apurge(cache.get_redis_client())


@pytest.mark.asyncio(loop_scope="function")
async def test_async_miss_does_not_slide_ttl():
    """异步镜像 test_miss_does_not_slide_ttl：miss 不滑动结构 TTL，只有命中刷新。"""
    cache = RedisFuncCache(uuid4().hex, LruPolicy, factory=async_redis_pool_factory, maxsize=8, ttl=60, update_ttl=True)
    await cache.policy.apurge(cache.get_redis_client())

    async def echo(x):
        return x

    decorated = cache.decorate()(echo)
    client = cache.get_redis_client()
    index_key, hmap_key = cache.policy.calc_key_pair(echo)

    assert await decorated("a") == "a"  # put：两侧 TTL 设为 60
    await asyncio.sleep(2)

    assert await decorated("b") == "b"  # miss：不应重置 TTL
    ttl_index = await client.ttl(index_key)
    ttl_hash = await client.ttl(hmap_key)
    assert 0 < ttl_index <= 58, f"miss 不应滑动 TTL，实际 {ttl_index}"
    assert 0 < ttl_hash <= 58, f"miss 不应滑动 TTL，实际 {ttl_hash}"

    await asyncio.sleep(1)
    assert await decorated("a") == "a"  # hit：TTL 重置回 ~60
    assert await client.ttl(index_key) >= 58
    assert await client.ttl(hmap_key) >= 58

    await cache.policy.apurge(cache.get_redis_client())


@pytest.mark.asyncio(loop_scope="function")
@pytest.mark.parametrize("cache_name,cache", list(ASYNC_CACHES.items()))
async def test_async_excludes(cache_name, cache):
    """异步镜像 test_excludes：excludes 排除的关键字参数不参与哈希。"""

    @cache(excludes=["pool"])
    async def get_data(pool, book_id: int):
        return f"book_{book_id}"

    assert await get_data(object(), book_id=123) == "book_123"
    with patch_object(cache, "aput") as mock_put:
        assert await get_data(object(), book_id=123) == "book_123"  # 不同 pool 同 book_id：命中
        mock_put.assert_not_called()


@pytest.mark.asyncio(loop_scope="function")
@pytest.mark.parametrize("cache_name,cache", list(ASYNC_CACHES.items()))
async def test_async_excludes_combined(cache_name, cache):
    """异步镜像：excludes 与 excludes_positional 组合。"""

    @cache(excludes=["config"], excludes_positional=[0])
    async def get_data(pool, user_id: int, book_id: int, config=None):
        return f"user_{user_id}_book_{book_id}"

    assert await get_data(object(), user_id=456, book_id=123, config={"timeout": 30}) == "user_456_book_123"
    with patch_object(cache, "aput") as mock_put:
        result = await get_data(object(), user_id=456, book_id=123, config={"timeout": 60})
        assert result == "user_456_book_123"
        mock_put.assert_not_called()


class Vertex:
    def __init__(self, value):
        self.value = value

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Vertex) and other.value == self.value


@pytest.mark.asyncio(loop_scope="function")
async def test_async_pickle_serializer_pair():
    """异步镜像 test_pickle：(dumps, loads) 对经 aget/aput 的往返。"""
    cache = RedisFuncCache(uuid4().hex, LruPolicy, factory=async_redis_pool_factory, maxsize=8)
    await cache.policy.apurge(cache.get_redis_client())
    cache.serializer = (pickle.dumps, pickle.loads)

    @cache
    async def echo(v):
        return v

    obj = Vertex(42)
    assert await echo(obj) == obj  # 写入并读回
    with patch_object(cache, "aput") as mock_put:
        assert await echo(obj) == obj  # 命中，反序列化得到相等对象
        mock_put.assert_not_called()


@pytest.mark.asyncio(loop_scope="function")
async def test_async_named_serializer_override():
    """装饰器 serializer= 覆盖（msgpack）在异步路径生效。"""
    cache = RedisFuncCache(uuid4().hex, LruPolicy, factory=async_redis_pool_factory, maxsize=8)
    await cache.policy.apurge(cache.get_redis_client())

    @cache(serializer="msgpack")
    async def get_data(x):
        return {"value": x}

    assert await get_data(7) == {"value": 7}
    with patch_object(cache, "aput") as mock_put:
        assert await get_data(7) == {"value": 7}
        mock_put.assert_not_called()
