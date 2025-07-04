from os import getenv
from typing import Callable, Dict, List
from warnings import warn

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
from redis_func_cache.policies.fifo import FifoClusterPolicy, FifoMultiplePolicy
from redis_func_cache.policies.lfu import LfuClusterPolicy, LfuMultiplePolicy
from redis_func_cache.policies.lru import LruClusterPolicy, LruMultiplePolicy, LruTClusterPolicy, LruTMultiplePolicy
from redis_func_cache.policies.mru import MruClusterPolicy, MruMultiplePolicy
from redis_func_cache.policies.rr import RrClusterPolicy, RrMultiplePolicy

try:
    from dotenv import load_dotenv
except ImportError as err:
    warn(f"{err} is not installed.")
else:
    load_dotenv()


def redis_factory(**kwargs):
    return Redis.from_url(REDIS_URL)


def async_redis_factory(**kwargs):
    return AsyncRedis.from_url(REDIS_URL)


MAXSIZE = 8

REDIS_URL = getenv("REDIS_URL", "redis://")
REDIS_CLUSTER_NODES = getenv("REDIS_CLUSTER_NODES")


CACHES = {
    "tlru": RedisFuncCache(__name__, LruTPolicy, client=redis_factory, maxsize=MAXSIZE),
    "lru": RedisFuncCache(__name__, LruPolicy, client=redis_factory, maxsize=MAXSIZE),
    "mru": RedisFuncCache(__name__, MruPolicy, client=redis_factory, maxsize=MAXSIZE),
    "rr": RedisFuncCache(__name__, RrPolicy, client=redis_factory, maxsize=MAXSIZE),
    "fifo": RedisFuncCache(__name__, FifoPolicy, client=redis_factory, maxsize=MAXSIZE),
    "lfu": RedisFuncCache(__name__, LfuPolicy, client=redis_factory, maxsize=MAXSIZE),
}

MULTI_CACHES = {
    "tlru": RedisFuncCache(__name__, LruTMultiplePolicy, client=redis_factory, maxsize=MAXSIZE),
    "lru": RedisFuncCache(__name__, LruMultiplePolicy, client=redis_factory, maxsize=MAXSIZE),
    "mru": RedisFuncCache(__name__, MruMultiplePolicy, client=redis_factory, maxsize=MAXSIZE),
    "rr": RedisFuncCache(__name__, RrMultiplePolicy, client=redis_factory, maxsize=MAXSIZE),
    "fifo": RedisFuncCache(__name__, FifoMultiplePolicy, client=redis_factory, maxsize=MAXSIZE),
    "lfu": RedisFuncCache(__name__, LfuMultiplePolicy, client=redis_factory, maxsize=MAXSIZE),
}


ASYNC_CACHES = {
    "tlru": RedisFuncCache(__name__, LruTPolicy, client=async_redis_factory, maxsize=MAXSIZE),
    "lru": RedisFuncCache(__name__, LruPolicy, client=async_redis_factory, maxsize=MAXSIZE),
    "mru": RedisFuncCache(__name__, MruPolicy, client=async_redis_factory, maxsize=MAXSIZE),
    "rr": RedisFuncCache(__name__, RrPolicy, client=async_redis_factory, maxsize=MAXSIZE),
    "fifo": RedisFuncCache(__name__, FifoPolicy, client=async_redis_factory, maxsize=MAXSIZE),
    "lfu": RedisFuncCache(__name__, LfuPolicy, client=async_redis_factory, maxsize=MAXSIZE),
}


ASYNC_MULTI_CACHES = {
    "tlru": RedisFuncCache(__name__, LruTMultiplePolicy, client=async_redis_factory, maxsize=MAXSIZE),
    "lru": RedisFuncCache(__name__, LruMultiplePolicy, client=async_redis_factory, maxsize=MAXSIZE),
    "mru": RedisFuncCache(__name__, MruMultiplePolicy, client=async_redis_factory, maxsize=MAXSIZE),
    "rr": RedisFuncCache(__name__, RrMultiplePolicy, client=async_redis_factory, maxsize=MAXSIZE),
    "fifo": RedisFuncCache(__name__, FifoMultiplePolicy, client=async_redis_factory, maxsize=MAXSIZE),
    "lfu": RedisFuncCache(__name__, LfuMultiplePolicy, client=async_redis_factory, maxsize=MAXSIZE),
}

CLUSTER_NODES: List[ClusterNode] = []
CLUSTER_CACHES: Dict[str, RedisFuncCache] = {}
if REDIS_CLUSTER_NODES:
    CLUSTER_NODES = [
        ClusterNode(cluster.split(":")[-2], int(cluster.split(":")[-1])) for cluster in REDIS_CLUSTER_NODES.split()
    ]
    REDIS_CLUSTER_FACTORY: Callable[[], RedisCluster] = lambda: RedisCluster(startup_nodes=CLUSTER_NODES)  # type: ignore[abstract]  # noqa: E731

    CLUSTER_CACHES = {
        "tlru": RedisFuncCache(__name__, LruTClusterPolicy, client=REDIS_CLUSTER_FACTORY, maxsize=MAXSIZE),
        "lru": RedisFuncCache(__name__, LruClusterPolicy, client=REDIS_CLUSTER_FACTORY, maxsize=MAXSIZE),
        "mru": RedisFuncCache(__name__, MruClusterPolicy, client=REDIS_CLUSTER_FACTORY, maxsize=MAXSIZE),
        "rr": RedisFuncCache(__name__, RrClusterPolicy, client=REDIS_CLUSTER_FACTORY, maxsize=MAXSIZE),
        "fifo": RedisFuncCache(__name__, FifoClusterPolicy, client=REDIS_CLUSTER_FACTORY, maxsize=MAXSIZE),
        "lfu": RedisFuncCache(__name__, LfuClusterPolicy, client=REDIS_CLUSTER_FACTORY, maxsize=MAXSIZE),
    }
    CLUSTER_MULTI_CACHES = {
        "tlru": RedisFuncCache(__name__, LruTClusterMultiplePolicy, client=REDIS_CLUSTER_FACTORY, maxsize=MAXSIZE),
        "lru": RedisFuncCache(__name__, LruClusterMultiplePolicy, client=REDIS_CLUSTER_FACTORY, maxsize=MAXSIZE),
        "mru": RedisFuncCache(__name__, MruClusterMultiplePolicy, client=REDIS_CLUSTER_FACTORY, maxsize=MAXSIZE),
        "rr": RedisFuncCache(__name__, RrClusterMultiplePolicy, client=REDIS_CLUSTER_FACTORY, maxsize=MAXSIZE),
        "fifo": RedisFuncCache(__name__, FifoClusterMultiplePolicy, client=REDIS_CLUSTER_FACTORY, maxsize=MAXSIZE),
        "lfu": RedisFuncCache(__name__, LfuClusterMultiplePolicy, client=REDIS_CLUSTER_FACTORY, maxsize=MAXSIZE),
    }
