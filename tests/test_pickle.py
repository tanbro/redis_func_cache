import json
import pickle
from random import randint
from unittest import TestCase, mock
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


def echo0(o):
    return o


def echo1(o):
    return o


class PicklePerFunctionSerializerTest(TestCase):
    def setUp(self):
        for cache in CACHES.values():
            cache.policy.purge()

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

            with self.assertRaisesRegex(TypeError, r".+"):
                for _ in range(randint(1, MAXSIZE * 2)):
                    obj = MyObject(uuid4())
                    echo_1(obj)

    def test_alternative_serializer(self):
        for cache in CACHES.values():
            for i in range(MAXSIZE):
                ser0_val = pickle.dumps(i)
                des0_val = i
                ser0 = mock.MagicMock(return_value=ser0_val)
                des0 = mock.MagicMock(return_value=des0_val)
                ser1_val = json.dumps(i).encode("utf-8")
                des1_val = i
                ser1 = mock.MagicMock(return_value=ser1_val)
                des1 = mock.MagicMock(return_value=des1_val)

                f0 = cache(echo0, serializer=ser0, deserializer=des0)
                f1 = cache(echo1, serializer=ser1, deserializer=des1)

                self.assertEqual(i, f0(i))
                ser0.assert_called_once_with(i)
                des0.assert_not_called()

                self.assertEqual(i, f1(i))
                ser1.assert_called_once_with(i)
                des1.assert_not_called()

                self.assertEqual(i, f0(i))
                des0.assert_called_once_with(ser0_val)

                self.assertEqual(i, f1(i))
                des1.assert_called_once_with(ser1_val)