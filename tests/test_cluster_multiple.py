from os import getenv
from random import randint
from unittest import TestCase

from redis.cluster import ClusterNode, RedisCluster

from redis_func_cache import (
    FifoClusterMultiplePolicy,
    LfuClusterMultiplePolicy,
    LruClusterMultiplePolicy,
    LruTClusterMultiplePolicy,
    MruClusterMultiplePolicy,
    RedisFuncCache,
    RrClusterMultiplePolicy,
)

REDIS_CLUSTER_NODES = getenv("REDIS_CLUSTER_NODES", "127.0.0.1:7000 127.0.0.1:7001 127.0.0.1:7002 127.0.0.1:7003")
CLUSTER_NODES = [
    ClusterNode(cluster.split(":")[0], int(cluster.split(":")[1])) for cluster in REDIS_CLUSTER_NODES.split()
]
REDIS_CLIENT: RedisCluster = RedisCluster(startup_nodes=CLUSTER_NODES)

MAXSIZE = 8
CACHES = {
    "tlru": RedisFuncCache(__name__, LruTClusterMultiplePolicy, client=REDIS_CLIENT, maxsize=MAXSIZE),
    "lru": RedisFuncCache(__name__, LruClusterMultiplePolicy, client=REDIS_CLIENT, maxsize=MAXSIZE),
    "mru": RedisFuncCache(__name__, MruClusterMultiplePolicy, client=REDIS_CLIENT, maxsize=MAXSIZE),
    "rr": RedisFuncCache(__name__, RrClusterMultiplePolicy, client=REDIS_CLIENT, maxsize=MAXSIZE),
    "fifo": RedisFuncCache(__name__, FifoClusterMultiplePolicy, client=REDIS_CLIENT, maxsize=MAXSIZE),
    "lfu": RedisFuncCache(__name__, LfuClusterMultiplePolicy, client=REDIS_CLIENT, maxsize=MAXSIZE),
}


class ClusterMultipleTest(TestCase):
    def setUp(self):
        for cache in CACHES.values():
            cache.policy.purge()

    def test_int(self):
        for cache in CACHES.values():

            @cache
            def echo(x):
                return x

            for i in range(randint(1, MAXSIZE * 2)):
                self.assertEqual(i, echo(i))
                self.assertEqual(i, echo(i))

    def test_two_functions(self):
        for cache in CACHES.values():

            @cache
            def echo1(x):
                return x

            @cache
            def echo2(x):
                return x

            for i in range(randint(MAXSIZE, MAXSIZE * 2)):
                self.assertEqual(i, echo1(i))
                self.assertEqual(i, echo2(i))
