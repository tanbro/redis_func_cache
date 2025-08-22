import pytest

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


# 保留此文件以备将来添加其他上下文相关的测试
# disabled, put_only, get_only 等测试已移至 test_cache_mode.py
