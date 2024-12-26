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


class PickleTest(TestCase):
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


class PicklePerFunctionSerializerTest(TestCase):
    def test_per_function_serializer(self):
        for cache in CACHES.values():

            @cache(serializer=pickle.dumps, deserializer=pickle.loads)
            def echo(o):
                return o

            for _ in range(randint(1, MAXSIZE * 2)):
                obj = MyObject(uuid4())
                self.assertEqual(obj, echo(obj))
                self.assertEqual(obj, echo(obj))

            @cache
            def echo_1(o):
                return o

            with self.assertRaisesRegex(TypeError, "Object of type MyObject is not JSON serializable"):
                for _ in range(randint(1, MAXSIZE * 2)):
                    obj = MyObject(uuid4())
                    echo_1(obj)

    def test_alternative_serializer(self):
        def echo(o):
            return o

        for cache in CACHES.values():
            for _ in range(randint(1, MAXSIZE * 2)):
                f0 = cache(echo)
                f1 = cache(echo, serializer=pickle.dumps, deserializer=pickle.loads)
                obj = MyObject(uuid4())
                with self.assertRaisesRegex(TypeError, "Object of type MyObject is not JSON serializable"):
                    f0(obj)
                self.assertEqual(obj, f1(obj))
                self.assertEqual(obj, f1(obj))
