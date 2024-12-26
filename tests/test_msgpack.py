from random import randint
from unittest import TestCase
from uuid import uuid4

from ._catches import CACHES, MAXSIZE


class MsgPackTest(TestCase):
    @classmethod
    def setUpClass(cls):
        for cache in CACHES.values():
            cache.serializer = "msgpack"

    def setUp(self):
        for cache in CACHES.values():
            cache.policy.purge()

    def test_one(self):
        for cache in CACHES.values():

            @cache
            def echo(o):
                return o

            for _ in range(randint(1, MAXSIZE * 2)):
                obj = uuid4().hex
                self.assertEqual(obj, echo(obj))
                self.assertEqual(obj, echo(obj))
