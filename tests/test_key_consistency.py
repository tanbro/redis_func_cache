"""键对一致性测试。

索引结构（zset 或 set）与 hash 键必须成对存在。单侧键丢失（如被手动删除、
或结构 TTL 到期时刻不一致）后，下一次 put 必须对称地重建两侧，且 ttl 配置
下两侧都获得 TTL。这锁定了 put 脚本中"多键 EXISTS + 对称 UNLINK/EXPIRE"的行为。
"""

from uuid import uuid4

import pytest

from redis_func_cache import RedisFuncCache
from redis_func_cache.policies.lru import LruPolicy
from redis_func_cache.policies.rr import RrPolicy

from ._catches import redis_factory


def _make_cache(policy, **kwargs):
    cache = RedisFuncCache(uuid4().hex, policy, factory=redis_factory, maxsize=8, **kwargs)

    def echo(x):
        return x

    return cache, cache.decorate()(echo), echo, cache.get_redis_client()


@pytest.mark.parametrize("policy", [LruPolicy(), RrPolicy()], ids=["lru", "rr"])
def test_rebuild_when_index_key_missing(policy):
    """索引键单独丢失后，下一次 put 重建两侧。"""
    cache, decorated, echo, client = _make_cache(policy)

    assert decorated("a") == "a"
    index_key, hmap_key = cache.policy.calc_keys(echo)
    client.delete(index_key)
    assert client.exists(index_key, hmap_key) == 1

    assert decorated("a") == "a"  # miss → put 重建
    assert client.exists(index_key, hmap_key) == 2
    assert cache.policy.get_size(redis_client=client) == 1


@pytest.mark.parametrize("policy", [LruPolicy(), RrPolicy()], ids=["lru", "rr"])
def test_rebuild_when_hash_key_missing(policy):
    """hash 键单独丢失后，下一次 put 重建两侧。"""
    cache, decorated, echo, client = _make_cache(policy)

    assert decorated("a") == "a"
    index_key, hmap_key = cache.policy.calc_keys(echo)
    client.delete(hmap_key)
    assert client.exists(index_key, hmap_key) == 1

    assert decorated("a") == "a"  # miss → put 重建
    assert client.exists(index_key, hmap_key) == 2
    assert cache.policy.get_size(redis_client=client) == 1


@pytest.mark.parametrize("policy", [LruPolicy(), RrPolicy()], ids=["lru", "rr"])
def test_rebuild_sets_ttl_on_both_keys(policy):
    """重建后，ttl>0 时两侧键都应获得 TTL（而不只是新建的那一侧）。"""
    cache, decorated, echo, client = _make_cache(policy, ttl=60)

    assert decorated("a") == "a"
    index_key, hmap_key = cache.policy.calc_keys(echo)
    client.delete(index_key)

    assert decorated("a") == "a"  # 重建
    assert 0 < client.ttl(index_key) <= 60
    assert 0 < client.ttl(hmap_key) <= 60


def test_both_keys_missing_recreates_cleanly():
    """两侧同时缺失（全新或全部过期）时，put 正常创建且 TTL 只设一次。"""
    cache, decorated, echo, client = _make_cache(LruPolicy(), ttl=60)

    assert decorated("a") == "a"
    index_key, hmap_key = cache.policy.calc_keys(echo)
    client.delete(index_key, hmap_key)

    assert decorated("a") == "a"
    assert client.exists(index_key, hmap_key) == 2
    assert 0 < client.ttl(index_key) <= 60
    assert 0 < client.ttl(hmap_key) <= 60
    assert cache.policy.get_size(redis_client=client) == 1


@pytest.mark.parametrize("policy", [LruPolicy(), RrPolicy()], ids=["lru", "rr"])
def test_get_size_reports_index_cardinality(policy):
    """get_size 报告索引基数（与 maxsize/驱逐口径一致），幽灵成员计入，孤儿字段不计入。

    行为变更：get_size 曾报告 HLEN（活字段数），与驱逐脚本使用的索引基数不一致。
    """
    cache, decorated, echo, client = _make_cache(policy)
    index_key, hmap_key = cache.policy.calc_keys(echo)
    hash_a = cache.policy.calc_hash(echo, ("a",), {})
    hash_b = cache.policy.calc_hash(echo, ("b",), {})

    assert decorated("a") == "a"
    assert decorated("b") == "b"
    assert cache.policy.get_size(redis_client=client) == 2

    # 字段过期 → 索引幽灵：get_size 保持 2（占用的驱逐 slot 不变），活字段数为 1
    client.hdel(hmap_key, hash_a)
    assert cache.policy.get_size(redis_client=client) == 2
    assert client.hlen(hmap_key) == 1

    cache.policy.vacuum(redis_client=client)
    assert cache.policy.get_size(redis_client=client) == 1

    # 索引成员丢失 → 孤儿字段：get_size 下降为 0（孤儿字段不再计入）
    if isinstance(policy, RrPolicy):
        client.srem(index_key, hash_b)
    else:
        client.zrem(index_key, hash_b)
    assert cache.policy.get_size(redis_client=client) == 0
    assert client.hlen(hmap_key) == 1
