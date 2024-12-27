from random import randint
from unittest import TestCase

from ._catches import MAXSIZE, MULTI_CACHES


class MultipleTest(TestCase):
    def setUp(self):
        for cache in MULTI_CACHES.values():
            cache.policy.purge()

    def test_int(self):
        for cache in MULTI_CACHES.values():

            @cache
            def echo(x):
                return x

            for i in range(randint(1, MAXSIZE * 2)):
                self.assertEqual(i, echo(i))
                self.assertEqual(i, echo(i))

    def test_two_functions(self):
        for cache in MULTI_CACHES.values():

            @cache
            def echo1(x):
                return x

            @cache
            def echo2(x):
                return x

            for i in range(randint(MAXSIZE, MAXSIZE * 2)):
                self.assertEqual(i, echo1(i))
                self.assertEqual(i, echo2(i))
