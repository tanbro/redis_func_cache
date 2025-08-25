from unittest.mock import patch
from uuid import uuid4

import pytest

from redis_func_cache.cache import RedisFuncCache

from ._catches import CACHES


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
def test_disable_rw(cache_name: str, cache: RedisFuncCache):  # noqa: F821
    """测试 disable_rw 上下文管理器是否正确禁用读写操作。"""

    @cache
    def echo(x):
        return x

    val = uuid4().hex
    # 正常调用，缓存应生效
    assert echo(val) == val
    with patch.object(cache, "put") as mock_put:
        assert cache.get_mode().read
        assert cache.get_mode().write
        assert echo(val) == val
        mock_put.assert_not_called()

    # 在 disable_rw 上下文中调用，函数仍然会被执行，但不会读写缓存
    with cache.disable_rw():
        assert not cache.get_mode().read
        assert not cache.get_mode().write
        # 直接调用函数，不经过缓存
        with patch.object(cache, "get") as mock_get:
            with patch.object(cache, "put") as mock_put:
                result = echo(val)  # 函数被执行，但不读写缓存
                # 确保 get 未被调用
                mock_get.assert_not_called()
                # 确保 put 未被调用
                mock_put.assert_not_called()
                # 确保返回值正确
                assert result == val

    # 离开上下文后，缓存应恢复正常
    with patch.object(cache, "get", return_value=cache.serialize(val)) as mock_get:
        with patch.object(cache, "put") as mock_put:
            result = echo(val)
            mock_get.assert_called_once()
            mock_put.assert_not_called()
            assert result == val


@pytest.mark.parametrize("cache_name,cache", CACHES.items())
def test_mode_cross_thread(cache_name: str, cache: RedisFuncCache):
    """测试 mode 在跨线程环境中的隔离性。"""
    from threading import Thread

    results = {}

    def thread_func():
        # 在子线程中，mode 应该是默认值（可读可写可执行）
        mode = cache.get_mode()
        results["thread_default_mode"] = (mode.read, mode.write, mode.exec)

    # 主线程中的 mode 测试
    main_initial_mode = cache.get_mode()

    # 启动子线程
    thread = Thread(target=thread_func)
    thread.start()
    thread.join()

    # 验证子线程执行结果
    assert "thread_default_mode" in results

    # 验证子线程中的 mode 隔离性
    assert results["thread_default_mode"] == (True, True, True)

    # 主线程中的 mode 测试
    main_after_thread_mode = cache.get_mode()

    # 验证主线程中的 mode 未受影响
    assert (main_initial_mode.read, main_initial_mode.write, main_initial_mode.exec) == (True, True, True)
    assert (main_after_thread_mode.read, main_after_thread_mode.write, main_after_thread_mode.exec) == (
        True,
        True,
        True,
    )
