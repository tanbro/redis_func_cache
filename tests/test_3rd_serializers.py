from datetime import datetime
from random import choice, randint, random
from unittest import TestCase
from uuid import uuid4

from ._catches import CACHES, MAXSIZE


def echo(x):
    return x


class SerializerByStringParameterTest(TestCase):
    def setUp(self):
        for cache in CACHES.values():
            cache.policy.purge()

    def _test_bytes(self, f):
        for _ in range(randint(1, MAXSIZE * 2)):
            v0 = uuid4().bytes
            v1 = f(v0)
            self.assertEqual(v0, v1)

    def _test_str(self, f):
        for _ in range(randint(1, MAXSIZE * 2)):
            v0 = uuid4().hex
            v1 = f(v0)
            self.assertEqual(v0, v1)

    def _test_int(self, f):
        for _ in range(randint(1, MAXSIZE * 2)):
            v0 = randint(-100 * MAXSIZE, MAXSIZE * 100)
            v1 = f(v0)
            self.assertEqual(v0, v1)

    def _test_float(self, f):
        for _ in range(randint(1, MAXSIZE * 2)):
            v0 = random()
            v1 = f(v0)
            self.assertEqual(v0, v1)

    def _test_bool(self, f):
        for _ in range(randint(1, MAXSIZE * 2)):
            v0 = choice([False, True])
            v1 = f(v0)
            self.assertEqual(v0, v1)

    def _test_none(self, f):
        for _ in range(randint(1, MAXSIZE * 2)):
            v0 = None
            v1 = f(v0)
            self.assertEqual(v0, v1)

    def _test_datetime(self, f):
        for _ in range(randint(1, MAXSIZE * 2)):
            v0 = datetime(
                randint(1900, 2100),
                randint(1, 12),
                randint(1, 28),
                randint(0, 23),
                randint(0, 59),
                randint(0, 59),
                randint(0, 999999),
                tzinfo=None,
            )
            v1 = f(v0)
            self.assertEqual(v0, v1)

    def test_bson(self):
        for cache in CACHES.values():
            fn = cache(echo, serializer="bson")
            self._test_bytes(fn)
            self._test_none(fn)
            self._test_bool(fn)
            self._test_str(fn)
            self._test_int(fn)
            self._test_float(fn)
            self._test_datetime(fn)

    def test_msgpack(self):
        for cache in CACHES.values():
            fn = cache(echo, serializer="msgpack")
            self._test_bytes(fn)
            self._test_none(fn)
            self._test_bool(fn)
            self._test_str(fn)
            self._test_int(fn)
            self._test_float(fn)

    def test_yaml(self):
        for cache in CACHES.values():
            fn = cache(echo, serializer="yaml")
            self._test_bytes(fn)
            self._test_none(fn)
            self._test_bool(fn)
            self._test_str(fn)
            self._test_int(fn)
            self._test_float(fn)
            self._test_datetime(fn)

    def test_cloudpickle(self):
        for cache in CACHES.values():
            fn = cache(echo, serializer="cloudpickle")
            self._test_bytes(fn)
            self._test_none(fn)
            self._test_bool(fn)
            self._test_str(fn)
            self._test_int(fn)
            self._test_float(fn)
            self._test_datetime(fn)
