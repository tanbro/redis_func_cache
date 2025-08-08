from random import randint

import pytest

from ._catches import MAXSIZE, MULTI_CACHES


@pytest.fixture(autouse=True)
def clean_caches():
    """自动清理缓存的夹具，在每个测试前后运行。"""
    # 测试前清理
    for cache in MULTI_CACHES.values():
        cache.policy.purge()
    yield
    # 测试后清理
    for cache in MULTI_CACHES.values():
        cache.policy.purge()


def test_multiple_int():
    for cache in MULTI_CACHES.values():

        @cache
        def echo(x):
            return x

        for i in range(randint(1, MAXSIZE * 2)):
            assert i == echo(i)
            assert i == echo(i)


def test_multiple_two_functions():
    for cache in MULTI_CACHES.values():

        @cache
        def echo1(x):
            return x

        @cache
        def echo2(x):
            return x

        for i in range(randint(1, MAXSIZE * 2)):
            assert i == echo1(i)
            assert i == echo2(i)
            assert i == echo1(i)
            assert i == echo2(i)
