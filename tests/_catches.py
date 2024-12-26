from os import getenv
from typing import Dict, List

from redis import Redis
from redis.asyncio import Redis as AsyncRedis
from redis.cluster import ClusterNode, RedisCluster

from redis_func_cache import (
    FifoClusterMultiplePolicy,
    FifoPolicy,
    LfuClusterMultiplePolicy,
    LfuPolicy,
    LruClusterMultiplePolicy,
    LruPolicy,
    LruTClusterMultiplePolicy,
    LruTPolicy,
    MruClusterMultiplePolicy,
    MruPolicy,
    RedisFuncCache,
    RrClusterMultiplePolicy,
    RrPolicy,
)

MAXSIZE = 8

REDIS_URL = getenv("REDIS_URL", "redis://")
REDIS_FACTORY = lambda: Redis.from_url(REDIS_URL)  # noqa: E731
ASYNC_REDIS_FACTORY = lambda: AsyncRedis.from_url(REDIS_URL)  # noqa: E731
REDIS_CLUSTER_NODES = getenv("REDIS_CLUSTER_NODES")


CACHES = {
    "tlru": RedisFuncCache(__name__, LruTPolicy, client=REDIS_FACTORY, maxsize=MAXSIZE),
    "lru": RedisFuncCache(__name__, LruPolicy, client=REDIS_FACTORY, maxsize=MAXSIZE),
    "mru": RedisFuncCache(__name__, MruPolicy, client=REDIS_FACTORY, maxsize=MAXSIZE),
    "rr": RedisFuncCache(__name__, RrPolicy, client=REDIS_FACTORY, maxsize=MAXSIZE),
    "fifo": RedisFuncCache(__name__, FifoPolicy, client=REDIS_FACTORY, maxsize=MAXSIZE),
    "lfu": RedisFuncCache(__name__, LfuPolicy, client=REDIS_FACTORY, maxsize=MAXSIZE),
}


ASYNC_CACHES = {
    "tlru": RedisFuncCache(__name__, LruTPolicy, client=ASYNC_REDIS_FACTORY, maxsize=MAXSIZE),
    "lru": RedisFuncCache(__name__, LruPolicy, client=ASYNC_REDIS_FACTORY, maxsize=MAXSIZE),
    "mru": RedisFuncCache(__name__, MruPolicy, client=ASYNC_REDIS_FACTORY, maxsize=MAXSIZE),
    "rr": RedisFuncCache(__name__, RrPolicy, client=ASYNC_REDIS_FACTORY, maxsize=MAXSIZE),
    "fifo": RedisFuncCache(__name__, FifoPolicy, client=ASYNC_REDIS_FACTORY, maxsize=MAXSIZE),
    "lfu": RedisFuncCache(__name__, LfuPolicy, client=ASYNC_REDIS_FACTORY, maxsize=MAXSIZE),
}

CLUSTER_NODES: List[ClusterNode] = []
CLUSTER_CACHES: Dict[str, RedisFuncCache] = {}
if REDIS_CLUSTER_NODES:
    CLUSTER_NODES = [
        ClusterNode(cluster.split(":")[0], int(cluster.split(":")[1])) for cluster in REDIS_CLUSTER_NODES.split()
    ]
    REDIS_CLIENT: RedisCluster = RedisCluster(startup_nodes=CLUSTER_NODES)

    CLUSTER_CACHES = {
        "tlru": RedisFuncCache(__name__, LruTClusterMultiplePolicy, client=REDIS_CLIENT, maxsize=MAXSIZE),
        "lru": RedisFuncCache(__name__, LruClusterMultiplePolicy, client=REDIS_CLIENT, maxsize=MAXSIZE),
        "mru": RedisFuncCache(__name__, MruClusterMultiplePolicy, client=REDIS_CLIENT, maxsize=MAXSIZE),
        "rr": RedisFuncCache(__name__, RrClusterMultiplePolicy, client=REDIS_CLIENT, maxsize=MAXSIZE),
        "fifo": RedisFuncCache(__name__, FifoClusterMultiplePolicy, client=REDIS_CLIENT, maxsize=MAXSIZE),
        "lfu": RedisFuncCache(__name__, LfuClusterMultiplePolicy, client=REDIS_CLIENT, maxsize=MAXSIZE),
    }
