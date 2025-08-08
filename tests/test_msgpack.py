from random import randint
from uuid import uuid4

import pytest

from ._catches import CACHES, MAXSIZE


@pytest.fixture(autouse=True)
def set_msgpack_serializer():
    """在测试前后设置和恢复 msgpack 序列化器。"""
    # 测试前设置
    original_serializers = {}
    for cache in CACHES.values():
        original_serializers[cache] = cache.serializer
        cache.serializer = "msgpack"
    yield
    # 测试后恢复
    for cache, serializer in original_serializers.items():
        cache.serializer = serializer


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


def test_msgpack_one():
    for cache in CACHES.values():

        @cache
        def echo(o):
            return o

        for _ in range(randint(1, MAXSIZE * 2)):
            obj = uuid4().hex
            assert obj == echo(obj)
            assert obj == echo(obj)
