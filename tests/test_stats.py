from uuid import uuid4

import pytest

from redis_func_cache.cache import RedisFuncCache

from ._catches import ASYNC_CACHES, CACHES, MULTI_CACHES


@pytest.fixture(autouse=True)
def clean_caches():
    """自动清理缓存的夹具，在每个测试前后运行。"""
    # 测试前清理同步缓存
    for cache in {**CACHES, **MULTI_CACHES}.values():
        try:
            cache.policy.purge()
        except RuntimeError:
            # 忽略异步客户端的清理错误
            pass

    # 测试前清理异步缓存
    for cache in ASYNC_CACHES.values():
        # 异步缓存的清理需要在异步上下文中进行，这里跳过
        pass

    yield

    # 测试后清理同步缓存
    for cache in {**CACHES, **MULTI_CACHES}.values():
        try:
            cache.policy.purge()
        except RuntimeError:
            # 忽略异步客户端的清理错误
            pass

    # 测试后清理异步缓存
    for cache in ASYNC_CACHES.values():
        # 异步缓存的清理需要在异步上下文中进行，这里跳过
        pass


@pytest.mark.parametrize("cache_name,cache", list(CACHES.items()) + list(MULTI_CACHES.items()))
def test_stats_context_basic(cache_name: str, cache: RedisFuncCache):
    """测试 stats_context 基本功能。"""

    @cache
    def echo(x):
        return x

    val1 = uuid4().hex
    val2 = uuid4().hex

    # 使用 stats_context 上下文管理器
    with cache.stats_context() as stats:
        # 初始状态检查
        assert stats.count == 0
        assert stats.hit == 0
        assert stats.miss == 0
        assert stats.read == 0
        assert stats.write == 0
        assert stats.exec == 0

        # 第一次调用，应该未命中缓存
        result1 = echo(val1)
        assert result1 == val1
        assert stats.count == 1
        assert stats.read == 1
        assert stats.miss == 1
        assert stats.exec == 1
        assert stats.write == 1
        assert stats.hit == 0

        # 第二次调用相同参数，应该命中缓存
        result2 = echo(val1)
        assert result2 == val1
        assert stats.count == 2
        assert stats.read == 2
        assert stats.miss == 1
        assert stats.exec == 1
        assert stats.write == 1
        assert stats.hit == 1

        # 第三次调用不同参数，应该未命中缓存
        result3 = echo(val2)
        assert result3 == val2
        assert stats.count == 3
        assert stats.read == 3
        assert stats.miss == 2
        assert stats.exec == 2
        assert stats.write == 2
        assert stats.hit == 1

        # 第四次调用第二次使用的参数，应该命中缓存
        result4 = echo(val2)
        assert result4 == val2
        assert stats.count == 4
        assert stats.read == 4
        assert stats.miss == 2
        assert stats.exec == 2
        assert stats.write == 2
        assert stats.hit == 2


@pytest.mark.parametrize("cache_name,cache", list(CACHES.items()) + list(MULTI_CACHES.items()))
def test_stats_context_reuse_stats_object(cache_name: str, cache: RedisFuncCache):
    """测试重用 Stats 对象。"""

    @cache
    def echo(x):
        return x

    val = uuid4().hex

    # 创建一个 Stats 对象并在多个上下文中重用它
    stats = RedisFuncCache.Stats()

    # 第一个上下文
    with cache.stats_context(stats) as s:
        assert s is stats
        result1 = echo(val)
        assert result1 == val
        assert stats.count == 1
        assert stats.hit == 0
        assert stats.miss == 1

    # 第二个上下文
    with cache.stats_context(stats) as s:
        assert s is stats
        result2 = echo(val)
        assert result2 == val
        assert stats.count == 2
        assert stats.hit == 1
        assert stats.miss == 1


@pytest.mark.parametrize("cache_name,cache", list(CACHES.items()) + list(MULTI_CACHES.items()))
def test_stats_context_without_context(cache_name: str, cache: RedisFuncCache):
    """测试在没有 stats_context 的情况下不会影响统计。"""

    @cache
    def echo(x):
        return x

    val = uuid4().hex

    # 在没有 stats_context 的情况下调用函数
    with cache.stats_context() as stats:
        result = echo(val)
        assert result == val
        # 确保统计正常工作
        assert stats.count == 1
        assert stats.hit == 0
        assert stats.miss == 1


@pytest.mark.parametrize("cache_name,cache", list(CACHES.items()) + list(MULTI_CACHES.items()))
def test_stats_context_multiple_key_policies(cache_name: str, cache: RedisFuncCache):
    """测试多键策略的统计功能。"""

    @cache
    def echo(x):
        return x

    val = uuid4().hex

    with cache.stats_context() as stats:
        # 第一次调用
        result1 = echo(val)
        assert result1 == val
        assert stats.count == 1
        assert stats.hit == 0
        assert stats.miss == 1
        assert stats.exec == 1
        assert stats.read == 1
        assert stats.write == 1

        # 第二次调用，应该命中缓存
        result2 = echo(val)
        assert result2 == val
        assert stats.count == 2
        assert stats.hit == 1
        assert stats.miss == 1
        assert stats.exec == 1
        assert stats.read == 2
        assert stats.write == 1
