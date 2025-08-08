import json
import pickle
from random import randint
from uuid import uuid4

import pytest

from ._catches import CACHES, MAXSIZE


class MyObject:
    def __init__(self, value):
        self.value = value

    def __eq__(self, value: object) -> bool:
        return self.value == value


@pytest.fixture(autouse=True)
def set_pickle_serializer():
    """在测试前后设置和恢复 pickle 序列化器。"""
    # 测试前设置
    original_serializers = {}
    for cache in CACHES.values():
        original_serializers[cache] = cache.serializer
        cache.serializer = pickle.dumps, pickle.loads
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


def test_pickle_object():
    for cache in CACHES.values():

        @cache
        def echo(o):
            return o

        for _ in range(randint(1, MAXSIZE * 2)):
            obj = MyObject(uuid4())
            assert obj == echo(obj)
            assert obj == echo(obj)


def test_pickle_lambda():
    for cache in CACHES.values():

        @cache
        def echo(f):
            return f

        for _ in range(randint(1, MAXSIZE * 2)):
            obj = lambda: uuid4()  # noqa: E731
            with pytest.raises(Exception):
                echo(obj)


def test_pickle_function():
    def my_func():
        return uuid4()

    for cache in CACHES.values():

        @cache
        def echo(f):
            return f

        for _ in range(randint(1, MAXSIZE * 2)):
            with pytest.raises(Exception):
                echo(my_func)


def test_pickle_builtin_function():
    for cache in CACHES.values():

        @cache
        def echo(f):
            return f

        for _ in range(randint(1, MAXSIZE * 2)):
            assert json.dumps == echo(json.dumps)


def test_pickle_builtin_type():
    for cache in CACHES.values():

        @cache
        def echo(f):
            return f

        for _ in range(randint(1, MAXSIZE * 2)):
            assert dict is echo(dict)
