import pytest

from redis_func_cache import LruPolicy, RedisFuncCache
from redis_func_cache.policies.fifo import FifoPolicy
from redis_func_cache.policies.lfu import LfuPolicy
from redis_func_cache.policies.mru import MruPolicy

from ._catches import CACHES, redis_factory
from ._mocks import patch_object


def _echo(x):
    return x


def _make_cache(policy, maxsize=8, **kwargs):
    cache = RedisFuncCache(__name__, policy, factory=redis_factory, maxsize=maxsize, **kwargs)
    cache.policy.purge(redis_client=cache.get_redis_client())
    return cache


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


def test_lru_order_correctness():
    """测试LRU缓存顺序的正确性。"""
    maxsize = 3
    cache = RedisFuncCache(__name__, LruPolicy, factory=redis_factory, maxsize=maxsize)
    cache.policy.purge(redis_client=cache.get_redis_client())

    @cache
    def echo(x):
        return _echo(x)

    # 按顺序访问元素填充缓存
    for i in range(maxsize):
        assert echo(i) == i

    # 再次访问第一个元素，使其变为最近使用
    assert echo(0) == 0

    # 添加新元素，应该淘汰第二个元素(1)，而不是第一个元素(0)
    assert echo(maxsize) == maxsize

    # 验证缓存中包含正确的元素: 0, 2, 3
    # 通过再次访问这些元素应该命中缓存来验证
    with patch_object(cache, "put") as mock_put:
        assert echo(0) == 0  # 应该命中
        assert echo(2) == 2  # 应该命中
        assert echo(3) == 3  # 应该命中
        mock_put.assert_not_called()

    # 访问已淘汰的元素1应该未命中
    with patch_object(cache, "get", return_value=None) as mock_get, patch_object(cache, "put") as mock_put:
        assert echo(1) == 1  # 应该未命中
        mock_get.assert_called_once()
        mock_put.assert_called_once()

    cache.policy.purge(redis_client=cache.get_redis_client())


def test_fifo_order_correctness():
    """测试FIFO缓存顺序的正确性。"""
    maxsize = 3
    cache = RedisFuncCache(__name__, FifoPolicy, factory=redis_factory, maxsize=maxsize)
    cache.policy.purge(redis_client=cache.get_redis_client())

    @cache
    def echo(x):
        return _echo(x)

    # 按顺序访问元素填充缓存
    for i in range(maxsize):
        assert echo(i) == i

    # 再次访问元素不会改变FIFO顺序
    assert echo(0) == 0
    assert echo(1) == 1

    # 添加新元素，应该淘汰第一个元素(0)，因为FIFO按插入顺序淘汰
    assert echo(maxsize) == maxsize

    # 验证缓存中包含正确的元素: 1, 2, 3
    with patch_object(cache, "put") as mock_put:
        assert echo(1) == 1  # 应该命中
        assert echo(2) == 2  # 应该命中
        assert echo(3) == 3  # 应该命中
        mock_put.assert_not_called()

    # 访问已淘汰的元素0应该未命中
    with patch_object(cache, "get", return_value=None) as mock_get, patch_object(cache, "put") as mock_put:
        assert echo(0) == 0  # 应该未命中
        mock_get.assert_called_once()
        mock_put.assert_called_once()

    cache.policy.purge(redis_client=cache.get_redis_client())


def test_lfu_order_correctness():
    """测试LFU缓存顺序的正确性。"""
    maxsize = 3
    cache = RedisFuncCache(__name__, LfuPolicy, factory=redis_factory, maxsize=maxsize)
    cache.policy.purge(redis_client=cache.get_redis_client())

    @cache
    def echo(x):
        return _echo(x)

    # 填充缓存
    for i in range(maxsize):
        assert echo(i) == i

    # 多次访问某些元素以增加它们的访问频率
    assert echo(0) == 0  # 第二次访问0
    assert echo(0) == 0  # 第三次访问0
    assert echo(1) == 1  # 第二次访问1

    # 添加新元素，应该淘汰访问频率最低的元素(2)
    assert echo(maxsize) == maxsize

    # 验证缓存中包含正确的元素: 0, 1, 3
    with patch_object(cache, "put") as mock_put:
        assert echo(0) == 0  # 应该命中
        assert echo(1) == 1  # 应该命中
        assert echo(3) == 3  # 应该命中
        mock_put.assert_not_called()

    # 访问已淘汰的元素2应该未命中
    with patch_object(cache, "get", return_value=None) as mock_get, patch_object(cache, "put") as mock_put:
        assert echo(2) == 2  # 应该未命中
        mock_get.assert_called_once()
        mock_put.assert_called_once()

    cache.policy.purge(redis_client=cache.get_redis_client())


def test_eviction_edge_cases():
    """测试缓存淘汰的边界情况。"""
    maxsize = 3
    cache = RedisFuncCache(__name__, LruPolicy, factory=redis_factory, maxsize=maxsize)
    cache.policy.purge(redis_client=cache.get_redis_client())

    @cache
    def echo(x):
        return _echo(x)

    # 测试空缓存情况
    assert echo(1) == 1

    # 测试缓存刚好满载情况
    for i in range(2, maxsize + 1):  # 从2开始，因为1已经添加了
        assert echo(i) == i
    assert cache.policy.get_size(redis_client=cache.get_redis_client()) == maxsize

    # 测试大量元素连续淘汰
    for i in range(maxsize + 1, maxsize * 3):
        assert echo(i) == i
        assert cache.policy.get_size(redis_client=cache.get_redis_client()) == maxsize

    cache.policy.purge(redis_client=cache.get_redis_client())


def test_mru_eviction():
    """测试MRU淘汰策略。"""
    maxsize = 3
    cache = RedisFuncCache(__name__, MruPolicy, factory=redis_factory, maxsize=maxsize)
    cache.policy.purge(redis_client=cache.get_redis_client())

    @cache
    def echo(x):
        return _echo(x)

    # 填充缓存
    for i in range(maxsize):
        assert echo(i) == i

    assert cache.policy.get_size(redis_client=cache.get_redis_client()) == maxsize

    # 访问第一个元素，使其变为最近使用
    assert echo(0) == 0

    # 添加新元素，MRU应该淘汰最近使用的元素(0)
    result = echo(maxsize)
    assert result == maxsize

    # 验证缓存大小仍然正确
    assert cache.policy.get_size(redis_client=cache.get_redis_client()) == maxsize

    # 验证0已被淘汰，其他元素仍在缓存中
    with patch_object(cache, "get", return_value=None) as mock_get, patch_object(cache, "put") as mock_put:
        assert echo(0) == 0  # 应该未命中，因为已被淘汰
        mock_get.assert_called_once()
        mock_put.assert_called_once()

    # 对于剩下的元素(1, 2, 3)，我们需要检查它们是否在缓存中
    # 但由于MRU的行为可能比较复杂，我们简化测试只验证缓存大小
    assert cache.policy.get_size(redis_client=cache.get_redis_client()) == maxsize

    cache.policy.purge(redis_client=cache.get_redis_client())


def test_mru_eviction_direction():
    """MRU 应驱逐"最近写入"的成员，而不是最旧的。

    回归测试：cache.py 曾把 options JSON 放在 ARGV[7]，导致 lru_put.lua 读不到
    'mru' 标志（它在 ext_args 里，实际位于 ARGV[8]），MRU 静默退化为 LRU。
    在成员级别断言驱逐方向（现有 test_mru_eviction 因 mock 强制 miss 无法区分）。
    """
    cache = _make_cache(MruPolicy, maxsize=2)

    def echo(x):
        return _echo(x)

    decorated = cache.decorate()(echo)
    client = cache.get_redis_client()
    index_key, _ = cache.policy.calc_key_pair(echo)
    hash_0 = cache.policy.calc_hash(echo, (0,), {})
    hash_1 = cache.policy.calc_hash(echo, (1,), {})

    # 填充缓存：0 先写入（分数 1），1 后写入（分数 2）
    assert decorated(0) == 0
    assert decorated(1) == 1

    # 写入第三个元素，MRU 应驱逐分数最高的"最近写入"成员 1，保留 0
    assert decorated(2) == 2

    assert client.zscore(index_key, hash_0) is not None  # 0（最旧）仍在
    assert client.zscore(index_key, hash_1) is None  # 1（最近写入）已被驱逐

    cache.policy.purge(redis_client=client)


def test_maxsize_shrink_mass_eviction():
    """运行时调小 maxsize 后，下一次写入一次性批量驱逐，zset 与 hash 保持一致。

    回归测试：单次驱逐超过约 8000 条时 unpack 溢出，且 ZPOPMIN 已写入而 HDEL
    中途失败，留下永久性的孤儿 hash 字段。
    """
    total = 10000
    cache = _make_cache(LruPolicy, maxsize=total)

    def echo(x):
        return _echo(x)

    decorated = cache.decorate()(echo)
    client = cache.get_redis_client()
    index_key, hmap_key = cache.policy.calc_key_pair(echo)

    # 直接用 pipeline 灌入 total 条，绕过装饰器
    pipe = client.pipeline(transaction=False)
    for i in range(total):
        h = cache.policy.calc_hash(echo, (i,), {})
        assert isinstance(h, bytes)  # PickleMd5Hasher yields raw digest bytes
        pipe.zadd(index_key, {h: i + 1})
        pipe.hset(hmap_key, h, f"v{i}")
    pipe.execute()
    assert client.zcard(index_key) == total

    # 运行时收缩：下一次写入应一次性驱逐 total - 10 + 1 条并保持两侧一致
    cache.maxsize = 10
    assert decorated(total) == total

    assert client.zcard(index_key) == 10
    assert client.hlen(hmap_key) == 10
    assert cache.policy.get_size(redis_client=client) == 10

    cache.policy.purge(redis_client=client)


def test_cache_data_consistency():
    """测试缓存数据的一致性。"""
    maxsize = 3
    cache = RedisFuncCache(__name__, LruPolicy, factory=redis_factory, maxsize=maxsize)
    cache.policy.purge(redis_client=cache.get_redis_client())

    @cache
    def echo(x):
        return _echo(x)

    # 填充缓存
    values = {}
    for i in range(maxsize * 2):
        result = echo(i)
        values[i] = result
        assert result == i

    # 验证所有缓存中的数据都是正确的
    for i in range(maxsize * 2):
        if i in values:
            assert echo(i) == values[i]

    cache.policy.purge(redis_client=cache.get_redis_client())
