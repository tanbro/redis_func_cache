from unittest.mock import patch
from uuid import uuid4

import pytest

from redis_func_cache import LruPolicy, RedisFuncCache

from ._catches import CACHES, redis_factory


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


@pytest.mark.parametrize("cache_name,cache", CACHES.items())
def test_excludes(cache_name, cache):
    """测试 excludes 参数，排除特定关键字参数。"""

    # 创建一个带有不可序列化参数的函数
    @cache(excludes=["pool"])
    def get_data(pool, book_id: int):
        return f"book_{book_id}"

    # 使用不同的 pool 对象但相同的 book_id，应该命中缓存
    pool1 = object()
    pool2 = object()

    # 第一次调用，应该执行函数并将结果存入缓存
    result1 = get_data(pool1, book_id=123)
    assert result1 == "book_123"

    # 第二次调用，使用不同的 pool 对象但相同的 book_id，应该命中缓存
    with patch.object(cache, "put") as mock_put:
        result2 = get_data(pool2, book_id=123)
        assert result2 == "book_123"
        # 确保没有再次调用 put 方法，表示命中了缓存
        mock_put.assert_not_called()


@pytest.mark.parametrize("cache_name,cache", CACHES.items())
def test_excludes_positional(cache_name, cache):
    """测试 excludes_positional 参数，排除特定位置参数。"""

    # 创建一个带有不可序列化参数的函数
    @cache(excludes_positional=[0])
    def get_data(pool, book_id: int):
        return f"book_{book_id}"

    # 使用不同的 pool 对象但相同的 book_id，应该命中缓存
    pool1 = object()
    pool2 = object()

    # 第一次调用，应该执行函数并将结果存入缓存
    result1 = get_data(pool1, book_id=123)
    assert result1 == "book_123"

    # 第二次调用，使用不同的 pool 对象但相同的 book_id，应该命中缓存
    with patch.object(cache, "put") as mock_put:
        result2 = get_data(pool2, book_id=123)
        assert result2 == "book_123"
        # 确保没有再次调用 put 方法，表示命中了缓存
        mock_put.assert_not_called()


@pytest.mark.parametrize("cache_name,cache", CACHES.items())
def test_excludes_and_excludes_positional_combined(cache_name, cache):
    """测试 excludes 和 excludes_positional 参数组合使用。"""

    # 创建一个带有多个不可序列化参数的函数
    @cache(excludes=["config"], excludes_positional=[0])
    def get_data(pool, user_id: int, book_id: int, config=None):
        return f"user_{user_id}_book_{book_id}"

    # 使用不同的 pool 对象和 config 但相同的 user_id 和 book_id，应该命中缓存
    pool1 = object()
    pool2 = object()
    config1 = {"timeout": 30}
    config2 = {"timeout": 60}

    # 第一次调用，应该执行函数并将结果存入缓存
    result1 = get_data(pool1, user_id=456, book_id=123, config=config1)
    assert result1 == "user_456_book_123"

    # 第二次调用，使用不同的 pool 对象和 config 但相同的 user_id 和 book_id，应该命中缓存
    with patch.object(cache, "put") as mock_put:
        result2 = get_data(pool2, user_id=456, book_id=123, config=config2)
        assert result2 == "user_456_book_123"
        # 确保没有再次调用 put 方法，表示命中了缓存
        mock_put.assert_not_called()


@pytest.mark.parametrize("cache_name,cache", CACHES.items())
def test_excludes_with_different_values(cache_name, cache):
    """测试 excludes 参数，确保排除的参数不同值不会影响缓存。"""

    # 创建一个带有不可序列化参数的函数
    @cache(excludes=["pool"])
    def get_data(pool, book_id: int):
        return f"book_{book_id}"

    # 使用相同的 book_id 但不同的 pool 对象，应该命中缓存
    pool1 = uuid4().hex
    pool2 = uuid4().hex

    # 第一次调用
    result1 = get_data(pool1, book_id=123)
    assert result1 == "book_123"

    # 第二次调用，使用不同的 pool 但相同的 book_id，应该命中缓存
    with patch.object(cache, "put") as mock_put:
        result2 = get_data(pool2, book_id=123)
        assert result2 == "book_123"
        mock_put.assert_not_called()

    # 第三次调用，使用相同的 pool 但不同的 book_id，应该未命中缓存
    with patch.object(cache, "put") as mock_put:
        result3 = get_data(pool1, book_id=456)
        assert result3 == "book_456"
        mock_put.assert_called_once()


def test_excludes_with_custom_cache():
    """测试在自定义缓存实例中使用 excludes 参数。"""
    custom_cache = RedisFuncCache(__name__, LruPolicy(), redis_factory=redis_factory, maxsize=10)
    custom_cache.policy.purge()

    @custom_cache(excludes=["session"])
    def get_user_data(session, user_id: int):
        return f"user_{user_id}_data"

    session1 = object()
    session2 = object()

    # 第一次调用
    result1 = get_user_data(session1, user_id=123)
    assert result1 == "user_123_data"

    # 第二次调用，使用不同的 session 但相同的 user_id，应该命中缓存
    with patch.object(custom_cache, "put") as mock_put:
        result2 = get_user_data(session2, user_id=123)
        assert result2 == "user_123_data"
        mock_put.assert_not_called()

    custom_cache.policy.purge()
