import pickle
from random import randint
from unittest import TestCase
from uuid import uuid4

from ._catches import CACHES, MAXSIZE


class MyObject:
    def __init__(self, value):
        self.value = value

    def __eq__(self, value: object) -> bool:
        return self.value == value


class PklRetvalTest(TestCase):
    @classmethod
    def setUpClass(cls):
        for cache in CACHES.values():
            cache.serializer = pickle.dumps, pickle.loads

    def setUp(self):
        for cache in CACHES.values():
            cache.policy.purge()

    def test_object(self):
        for cache in CACHES.values():

            @cache
            def echo(o):
                return o

            for _ in range(randint(1, MAXSIZE * 2)):
                obj = MyObject(uuid4())
                self.assertEqual(obj, echo(obj))
                self.assertEqual(obj, echo(obj))
