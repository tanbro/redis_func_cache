from random import randint

import pytest

from ._catches import CLUSTER_CACHES, MAXSIZE, REDIS_CLUSTER_NODES


@pytest.fixture(autouse=True)
def clean_caches():
    """自动清理缓存的夹具，在每个测试前后运行。"""
    # 测试前清理
    for cache in CLUSTER_CACHES.values():
        cache.policy.purge()
    yield
    # 测试后清理
    for cache in CLUSTER_CACHES.values():
        cache.policy.purge()


@pytest.mark.skipif(not REDIS_CLUSTER_NODES, reason="REDIS_CLUSTER_NODES environment variable is not set")
def test_cluster_int():
    for cache in CLUSTER_CACHES.values():

        @cache
        def echo(x):
            return x

        for i in range(randint(1, MAXSIZE * 2)):
            assert i == echo(i)
            assert i == echo(i)


@pytest.mark.skipif(not REDIS_CLUSTER_NODES, reason="REDIS_CLUSTER_NODES environment variable is not set")
def test_cluster_two_functions():
    for cache in CLUSTER_CACHES.values():

        @cache
        def echo1(x):
            return x

        @cache
        def echo2(x):
            return x

        for i in range(randint(1, MAXSIZE * 2)):  # 修改为统一使用相同的随机范围
            assert i == echo1(i)
            assert i == echo2(i)
            assert i == echo1(i)
            assert i == echo2(i)
