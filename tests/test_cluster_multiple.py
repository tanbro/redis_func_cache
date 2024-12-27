from random import randint
from unittest import TestCase, skipUnless

from ._catches import CLUSTER_MULTI_CACHES, MAXSIZE, REDIS_CLUSTER_NODES


@skipUnless(REDIS_CLUSTER_NODES, "REDIS_CLUSTER_NODES environment variable is not set")
class ClusterMultipleTest(TestCase):
    def setUp(self):
        for cache in CLUSTER_MULTI_CACHES.values():
            cache.policy.purge()

    def test_int(self):
        for cache in CLUSTER_MULTI_CACHES.values():

            @cache
            def echo(x):
                return x

            for i in range(randint(1, MAXSIZE * 2)):
                self.assertEqual(i, echo(i))
                self.assertEqual(i, echo(i))

    def test_two_functions(self):
        for cache in CLUSTER_MULTI_CACHES.values():

            @cache
            def echo1(x):
                return x

            @cache
            def echo2(x):
                return x

            for i in range(randint(MAXSIZE, MAXSIZE * 2)):
                self.assertEqual(i, echo1(i))
                self.assertEqual(i, echo2(i))
