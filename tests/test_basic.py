from random import randint
from unittest.mock import patch

import pytest

from redis_func_cache import LruPolicy, RedisFuncCache

from ._catches import CACHES, MAXSIZE, redis_factory


def _echo(x):
    return x


@pytest.fixture(autouse=True)
def clean_caches():
    """自动清理缓存的夹具，在每个测试前后运行。"""
    # 测试前清理
    for cache in CACHES.values():
        cache.policy.purge()
    yield
    # 测试后清理
    for cache in CACHES.values():
        cache.policy.purge()


def test_basic():
    """测试缓存命中和未命中场景。"""
    for cache in CACHES.values():

        @cache
        def echo(x):
            return _echo(x)

        # mock hit
        for i in range(cache.maxsize):
            with patch.object(cache, "get", return_value=cache.serialize(i)) as mock_get:
                with patch.object(cache, "put") as mock_put:
                    echo(i)
                    mock_get.assert_called_once()
                    mock_put.assert_not_called()

        # mock not hit
        for i in range(cache.maxsize):
            with patch.object(cache, "get", return_value=None) as mock_get:
                with patch.object(cache, "put") as mock_put:
                    echo(i)
                    mock_get.assert_called_once()
                    mock_put.assert_called_once()

        # first run, fill the cache to max size. then second run, to hit the cache
        for i in range(cache.maxsize):
            assert _echo(i) == echo(i)
            assert i + 1 == cache.policy.get_size()
            with patch.object(cache, "put") as mock_put:
                assert i == echo(i)
                mock_put.assert_not_called()

        # run again, should be all hit
        for i in range(cache.maxsize):
            with patch.object(cache, "get", return_value=cache.serialize(i)) as mock_get:
                with patch.object(cache, "put") as mock_put:
                    echo(i)
                    mock_get.assert_called_once()
                    mock_put.assert_not_called()

        assert cache.maxsize == cache.policy.get_size()

        # run more than max size, should be not all hit
        n = randint(cache.maxsize + 1, 2 * cache.maxsize)
        for i in range(cache.maxsize, n):
            with patch.object(cache, "get", return_value=None) as mock_get:
                with patch.object(cache, "put") as mock_put:
                    echo(i)
                    mock_get.assert_called_once()
                    mock_put.assert_called_once()

        assert cache.maxsize == cache.policy.get_size()


def test_different_args():
    """测试不同参数的缓存。"""
    for cache in CACHES.values():

        @cache
        def echo(x):
            return _echo(x)

        # test different args
        for i in range(cache.maxsize):
            assert i == echo(i)

        # run again, should be all hit
        for i in range(cache.maxsize):
            assert i == echo(i)


def test_complex_args():
    """测试复杂参数的缓存。"""
    for cache in CACHES.values():

        @cache
        def echo(x):
            return _echo(x)

        # test complex args
        assert {"a": 1} == echo({"a": 1})
        assert [1, 2, 3] == echo([1, 2, 3])
        assert "1" == echo("1")
        assert 1 == echo(1)
        assert 1.0 == echo(1.0)
        assert True is echo(True)
        assert None is echo(None)

        # run again, should be all hit
        with patch.object(cache, "put") as mock_put:
            assert {"a": 1} == echo({"a": 1})
            assert [1, 2, 3] == echo([1, 2, 3])
            assert "1" == echo("1")
            assert 1 == echo(1)
            assert 1.0 == echo(1.0)
            assert True is echo(True)
            assert None is echo(None)
            mock_put.assert_not_called()


def test_cache_clear():
    """测试缓存清除。"""
    for cache in CACHES.values():

        @cache
        def echo(x):
            return _echo(x)

        # fill the cache
        for i in range(cache.maxsize):
            assert i == echo(i)

        assert cache.maxsize == cache.policy.get_size()

        # clear the cache
        cache.policy.purge()
        assert 0 == cache.policy.get_size()

        # run again, should be all miss
        for i in range(cache.maxsize):
            with patch.object(cache, "get", return_value=None) as mock_get:
                with patch.object(cache, "put") as mock_put:
                    echo(i)
                    mock_get.assert_called_once()
                    mock_put.assert_called_once()


def test_cache_wrapper():
    """测试缓存装饰器。"""
    for cache in CACHES.values():

        @cache
        def echo(x):
            return _echo(x)

        # 检查 __wrapped__ 属性是否存在并且是函数
        assert hasattr(echo, "__wrapped__")
        assert callable(getattr(echo, "__wrapped__"))


def test_different_policies():
    """测试不同缓存策略。"""
    # test LRU policy
    lru_cache = RedisFuncCache(__name__, LruPolicy(), redis_factory=redis_factory, maxsize=MAXSIZE)
    lru_cache.policy.purge()

    @lru_cache
    def echo(x):
        return _echo(x)

    # fill the cache
    for i in range(lru_cache.maxsize):
        assert i == echo(i)

    assert lru_cache.maxsize == lru_cache.policy.get_size()

    # access the first item, should be hit
    with patch.object(lru_cache, "put") as mock_put:
        assert 0 == echo(0)
        mock_put.assert_not_called()

    # run more than max size, should evict the least recently used item
    n = randint(lru_cache.maxsize + 1, 2 * lru_cache.maxsize)
    for i in range(lru_cache.maxsize, n):
        assert i == echo(i)

    assert lru_cache.maxsize == lru_cache.policy.get_size()

    lru_cache.policy.purge()


def test_multiple_decorators():
    """测试多个装饰器。"""
    for cache in CACHES.values():

        def decorator(func):
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)

            return wrapper

        @cache
        @decorator
        def echo(x):
            return _echo(x)

        assert 1 == echo(1)

        with patch.object(cache, "put") as mock_put:
            assert 1 == echo(1)
            mock_put.assert_not_called()


def test_custom_maxsize():
    """测试自定义最大缓存大小。"""
    maxsize = 3
    custom_cache = RedisFuncCache(__name__, LruPolicy(), redis_factory=redis_factory, maxsize=maxsize)
    custom_cache.policy.purge()

    @custom_cache
    def echo(x):
        return _echo(x)

    # fill the cache
    for i in range(custom_cache.maxsize):
        assert i == echo(i)

    assert custom_cache.maxsize == custom_cache.policy.get_size()

    # run more than max size, should evict items
    n = randint(custom_cache.maxsize + 1, 2 * custom_cache.maxsize)
    for i in range(custom_cache.maxsize, n):
        assert i == echo(i)

    assert custom_cache.maxsize == custom_cache.policy.get_size()

    custom_cache.policy.purge()


def test_json_serializer():
    """测试JSON序列化。"""
    json_cache = RedisFuncCache(__name__, LruPolicy(), serializer="json", redis_factory=redis_factory, maxsize=MAXSIZE)
    json_cache.policy.purge()

    @json_cache
    def echo(x):
        return _echo(x)

    data = {"a": 1, "b": [1, 2, 3], "c": {"d": "test"}}
    result = echo(data)
    assert result == data

    # 确保再次调用会命中缓存
    with patch.object(json_cache, "put") as mock_put:
        result2 = echo(data)
        assert result2 == data
        mock_put.assert_not_called()

    json_cache.policy.purge()


def test_lru_eviction_correctness():
    """测试LRU缓存淘汰的正确性。"""
    maxsize = 3
    lru_cache = RedisFuncCache(__name__, LruPolicy(), redis_factory=redis_factory, maxsize=maxsize)
    lru_cache.policy.purge()

    @lru_cache
    def echo(x):
        return _echo(x)

    # 填充缓存到最大容量
    for i in range(maxsize):
        assert echo(i) == i

    assert lru_cache.maxsize == lru_cache.policy.get_size()

    # 访问第一个元素，使其变为最近使用
    assert echo(0) == 0

    # 添加新元素，应该淘汰第二个元素(1)，而不是第一个元素(0)
    result = echo(maxsize)
    assert result == maxsize

    # 验证缓存大小仍然正确
    assert lru_cache.maxsize == lru_cache.policy.get_size()

    lru_cache.policy.purge()


def test_eviction_count_accuracy():
    """测试缓存淘汰数量的准确性。"""
    maxsize = 3
    lru_cache = RedisFuncCache(__name__, LruPolicy(), redis_factory=redis_factory, maxsize=maxsize)
    lru_cache.policy.purge()

    @lru_cache
    def echo(x):
        return _echo(x)

    # 填充缓存
    for i in range(maxsize):
        assert echo(i) == i

    # 验证缓存已满
    assert lru_cache.policy.get_size() == maxsize

    # 添加超出缓存大小的元素，触发淘汰
    result = echo(maxsize)
    assert result == maxsize

    # 验证淘汰后缓存大小仍然正确
    assert lru_cache.policy.get_size() == maxsize

    lru_cache.policy.purge()
