from datetime import datetime
from random import choice, randint, random
from uuid import uuid4

import pytest

from ._catches import CACHES, MAXSIZE


def echo(x):
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


def test_bson():
    def _test_bytes(f):
        for _ in range(randint(1, MAXSIZE * 2)):
            v0 = uuid4().bytes
            v1 = f(v0)
            assert v0 == v1

    def _test_str(f):
        for _ in range(randint(1, MAXSIZE * 2)):
            v0 = uuid4().hex
            v1 = f(v0)
            assert v0 == v1

    def _test_int(f):
        for _ in range(randint(1, MAXSIZE * 2)):
            v0 = randint(-(2**63), 2**63 - 1)
            v1 = f(v0)
            assert v0 == v1

    def _test_float(f):
        for _ in range(randint(1, MAXSIZE * 2)):
            v0 = random()
            v1 = f(v0)
            assert v0 == v1

    def _test_bool(f):
        for _ in range(randint(1, MAXSIZE * 2)):
            v0 = choice((True, False))
            v1 = f(v0)
            assert v0 == v1

    def _test_none(f):
        for _ in range(randint(1, MAXSIZE * 2)):
            v0 = None
            v1 = f(v0)
            assert v0 == v1

    def _test_datetime(f):
        for _ in range(randint(1, MAXSIZE * 2)):
            v0 = datetime.now().replace(microsecond=0)
            v1 = f(v0)
            assert v0 == v1

    for cache in CACHES.values():
        fn = cache(echo, serializer="bson")
        _test_bytes(fn)
        _test_none(fn)
        _test_bool(fn)
        _test_str(fn)
        _test_int(fn)
        _test_float(fn)
        _test_datetime(fn)


def test_msgpack():
    def _test_bytes(f):
        for _ in range(randint(1, MAXSIZE * 2)):
            v0 = uuid4().bytes
            v1 = f(v0)
            assert v0 == v1

    def _test_str(f):
        for _ in range(randint(1, MAXSIZE * 2)):
            v0 = uuid4().hex
            v1 = f(v0)
            assert v0 == v1

    def _test_int(f):
        for _ in range(randint(1, MAXSIZE * 2)):
            v0 = randint(-(2**63), 2**63 - 1)
            v1 = f(v0)
            assert v0 == v1

    def _test_float(f):
        for _ in range(randint(1, MAXSIZE * 2)):
            v0 = random()
            v1 = f(v0)
            assert v0 == v1

    def _test_bool(f):
        for _ in range(randint(1, MAXSIZE * 2)):
            v0 = choice((True, False))
            v1 = f(v0)
            assert v0 == v1

    def _test_none(f):
        for _ in range(randint(1, MAXSIZE * 2)):
            v0 = None
            v1 = f(v0)
            assert v0 == v1

    for cache in CACHES.values():
        fn = cache(echo, serializer="msgpack")
        _test_bytes(fn)
        _test_none(fn)
        _test_bool(fn)
        _test_str(fn)
        _test_int(fn)
        _test_float(fn)


def test_yaml():
    def _test_bytes(f):
        for _ in range(randint(1, MAXSIZE * 2)):
            v0 = uuid4().bytes
            v1 = f(v0)
            assert v0 == v1

    def _test_str(f):
        for _ in range(randint(1, MAXSIZE * 2)):
            v0 = uuid4().hex
            v1 = f(v0)
            assert v0 == v1

    def _test_int(f):
        for _ in range(randint(1, MAXSIZE * 2)):
            v0 = randint(-(2**63), 2**63 - 1)
            v1 = f(v0)
            assert v0 == v1

    def _test_float(f):
        for _ in range(randint(1, MAXSIZE * 2)):
            v0 = random()
            v1 = f(v0)
            assert v0 == v1

    def _test_bool(f):
        for _ in range(randint(1, MAXSIZE * 2)):
            v0 = choice((True, False))
            v1 = f(v0)
            assert v0 == v1

    def _test_none(f):
        for _ in range(randint(1, MAXSIZE * 2)):
            v0 = None
            v1 = f(v0)
            assert v0 == v1

    def _test_datetime(f):
        for _ in range(randint(1, MAXSIZE * 2)):
            v0 = datetime.now().replace(microsecond=0)
            v1 = f(v0)
            assert v0 == v1

    for cache in CACHES.values():
        fn = cache(echo, serializer="yaml")
        _test_bytes(fn)
        _test_none(fn)
        _test_bool(fn)
        _test_str(fn)
        _test_int(fn)
        _test_float(fn)
        _test_datetime(fn)


def test_cloudpickle():
    def _test_bytes(f):
        for _ in range(randint(1, MAXSIZE * 2)):
            v0 = uuid4().bytes
            v1 = f(v0)
            assert v0 == v1

    def _test_str(f):
        for _ in range(randint(1, MAXSIZE * 2)):
            v0 = uuid4().hex
            v1 = f(v0)
            assert v0 == v1

    def _test_int(f):
        for _ in range(randint(1, MAXSIZE * 2)):
            v0 = randint(-(2**63), 2**63 - 1)
            v1 = f(v0)
            assert v0 == v1

    def _test_float(f):
        for _ in range(randint(1, MAXSIZE * 2)):
            v0 = random()
            v1 = f(v0)
            assert v0 == v1

    def _test_bool(f):
        for _ in range(randint(1, MAXSIZE * 2)):
            v0 = choice((True, False))
            v1 = f(v0)
            assert v0 == v1

    def _test_none(f):
        for _ in range(randint(1, MAXSIZE * 2)):
            v0 = None
            v1 = f(v0)
            assert v0 == v1

    def _test_datetime(f):
        for _ in range(randint(1, MAXSIZE * 2)):
            v0 = datetime.now().replace(microsecond=0)
            v1 = f(v0)
            assert v0 == v1

    for cache in CACHES.values():
        fn = cache(echo, serializer="cloudpickle")
        _test_bytes(fn)
        _test_none(fn)
        _test_bool(fn)
        _test_str(fn)
        _test_int(fn)
        _test_float(fn)
        _test_datetime(fn)
