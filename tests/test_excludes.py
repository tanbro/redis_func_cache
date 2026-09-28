from uuid import uuid4

import pytest

from redis_func_cache import RedisFuncCache, lru_policy

from ._catches import CACHES, redis_factory
from ._mocks import patch_object


@pytest.fixture(autouse=True)
def clean_caches():
    """自动清理缓存的夹具，在每个测试前后运行。"""
    # 测试前清理
    for cache in CACHES.values():
        cache.purge()
    yield
    # 测试后清理
    for cache in CACHES.values():
        cache.purge()


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
    with patch_object(cache.policy, "put") as mock_put:
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
    with patch_object(cache.policy, "put") as mock_put:
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
    with patch_object(cache.policy, "put") as mock_put:
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
    with patch_object(cache.policy, "put") as mock_put:
        result2 = get_data(pool2, book_id=123)
        assert result2 == "book_123"
        mock_put.assert_not_called()

    # 第三次调用，使用相同的 pool 但不同的 book_id，应该未命中缓存
    with patch_object(cache.policy, "put") as mock_put:
        result3 = get_data(pool1, book_id=456)
        assert result3 == "book_456"
        mock_put.assert_called_once()


@pytest.mark.parametrize("cache_name,cache", CACHES.items())
def test_excludes_positional_with_varargs(cache_name, cache):
    """varargs 函数上 excludes_positional 应按展开后的位置实参过滤。

    当前实现经 ``sig.bind`` 后整个 ``*args`` 折叠为单个 ``args`` 条目，
    ``excludes_positional=[0]`` 会把它整体删除，导致所有调用共享同一 hash。
    """
    call_count = 0

    @cache(excludes_positional=[0])
    def get_data(*args):
        nonlocal call_count
        call_count += 1
        return f"book_{args[1]}"

    # 第一次调用，args[0] 被排除，args[1] 参与哈希
    result1 = get_data(object(), 123)
    assert result1 == "book_123"
    assert call_count == 1

    # args[0] 不同、args[1] 相同，应命中缓存
    with patch_object(cache.policy, "put") as mock_put:
        result2 = get_data(object(), 123)
        assert result2 == "book_123"
        mock_put.assert_not_called()
    assert call_count == 1

    # args[1] 不同，应未命中缓存（当前实现下会错误命中并返回 book_123）
    with patch_object(cache.policy, "put") as mock_put:
        result3 = get_data(object(), 456)
        assert result3 == "book_456"
        mock_put.assert_called_once()
    assert call_count == 2


@pytest.mark.parametrize("cache_name,cache", CACHES.items())
def test_excludes_positional_varargs_not_folded(cache_name, cache):
    """具名参数 + varargs 混合时，位置过滤只摘除单个 varargs 元素。"""

    @cache(excludes_positional=[1])
    def get_data(pool, *args):
        return f"book_{args[0]}"

    result1 = get_data("pool1", 123)
    assert result1 == "book_123"

    # args[0] 被排除、pool 相同 → 应命中缓存（*args 未被整体删除，pool 仍参与哈希）
    with patch_object(cache.policy, "put") as mock_put:
        result2 = get_data("pool1", 456)
        assert result2 == "book_123"
        mock_put.assert_not_called()

    # pool 不同 → 应未命中
    with patch_object(cache.policy, "put") as mock_put:
        result3 = get_data("pool2", 456)
        assert result3 == "book_456"
        mock_put.assert_called_once()


@pytest.mark.parametrize("cache_name,cache", CACHES.items())
def test_excludes_matches_kwds_keys(cache_name, cache):
    """``**kwargs`` 收到的键可被 excludes 按名排除。"""

    @cache(excludes=["conn"])
    def get_data(**kwds):
        return f"book_{kwds['book_id']}"

    result1 = get_data(book_id=123, conn=object())
    assert result1 == "book_123"

    with patch_object(cache.policy, "put") as mock_put:
        result2 = get_data(book_id=123, conn=object())
        assert result2 == "book_123"
        mock_put.assert_not_called()

    with patch_object(cache.policy, "put") as mock_put:
        result3 = get_data(book_id=456, conn=object())
        assert result3 == "book_456"
        mock_put.assert_called_once()


@pytest.mark.parametrize("cache_name,cache", CACHES.items())
def test_excludes_catch_all_raises(cache_name, cache):
    """catch-all 参数本身不可整体排除，应显式抛 TypeError。"""

    @cache(excludes=["args"])
    def f(*args):
        return "ok"

    with pytest.raises(TypeError, match="catch-all"):
        f(1)

    @cache(excludes=["kwds"])
    def g(**kwds):
        return "ok"

    with pytest.raises(TypeError, match="catch-all"):
        g(x=1)


@pytest.mark.parametrize("cache_name,cache", CACHES.items())
def test_excludes_positional_out_of_range_raises(cache_name, cache):
    """excludes_positional 下标越界应显式抛 TypeError，而非静默忽略。"""

    @cache(excludes_positional=[5])
    def get_data(*args):
        return "ok"

    with pytest.raises(TypeError, match="out of range"):
        get_data(1, 2)


def test_excludes_positional_keyword_only_never_indexed():
    """keyword-only 参数不占位置下标，位置下标指向展开位置流（bound.args）。"""

    custom_cache = RedisFuncCache("kwonly-positional-test", lru_policy, factory=redis_factory, maxsize=10)
    custom_cache.purge()

    @custom_cache(excludes_positional=[0])
    def get_data(pool, *, book_id: int):
        return f"book_{book_id}"

    result1 = get_data(object(), book_id=123)
    assert result1 == "book_123"

    # pool（位置流下标 0）被排除，book_id 是 keyword-only 不占下标
    with patch_object(custom_cache.policy, "put") as mock_put:
        result2 = get_data(object(), book_id=123)
        assert result2 == "book_123"
        mock_put.assert_not_called()

    with patch_object(custom_cache.policy, "put") as mock_put:
        result3 = get_data(object(), book_id=456)
        assert result3 == "book_456"
        mock_put.assert_called_once()

    custom_cache.purge()


def test_excludes_equivalence_invariance():
    """同一逻辑调用（按位置传 vs 按关键字传）应产生相同的缓存身份。"""
    custom_cache = RedisFuncCache("equivalence-test", lru_policy, factory=redis_factory, maxsize=10)
    custom_cache.purge()

    @custom_cache(excludes_positional=[0])
    def get_data(pool, book_id: int):
        return f"book_{book_id}"

    result1 = get_data(object(), 123)
    assert result1 == "book_123"

    # f(1, 2) 与 f(a=1, b=2) 的 bound.args 相同，应命中同一条缓存
    with patch_object(custom_cache.policy, "put") as mock_put:
        result2 = get_data(pool=object(), book_id=123)
        assert result2 == "book_123"
        mock_put.assert_not_called()

    custom_cache.purge()


def test_excludes_with_custom_cache():
    """测试在自定义缓存实例中使用 excludes 参数。"""
    custom_cache = RedisFuncCache(__name__, lru_policy, factory=redis_factory, maxsize=10)
    custom_cache.purge()

    @custom_cache(excludes=["session"])
    def get_user_data(session, user_id: int):
        return f"user_{user_id}_data"

    session1 = object()
    session2 = object()

    # 第一次调用
    result1 = get_user_data(session1, user_id=123)
    assert result1 == "user_123_data"

    # 第二次调用，使用不同的 session 但相同的 user_id，应该命中缓存
    with patch_object(custom_cache.policy, "put") as mock_put:
        result2 = get_user_data(session2, user_id=123)
        assert result2 == "user_123_data"
        mock_put.assert_not_called()

    custom_cache.purge()
