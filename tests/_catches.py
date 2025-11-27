import asyncio
import atexit
from os import getenv
from typing import Callable, Dict, List, Optional
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


redis_client: Optional[Redis] = None
async_redis_client: Optional[AsyncRedis] = None


def redis_factory(**kwargs):
    global redis_client
    if redis_client is None:
        redis_client = Redis.from_url(REDIS_URL)
    return redis_client


def async_redis_factory(**kwargs):
    global async_redis_client
    if async_redis_client is None:
        async_redis_client = AsyncRedis.from_url(REDIS_URL)
    return async_redis_client


async def close_async_redis_client():
    """关闭全局异步Redis客户端连接"""
    global async_redis_client
    if async_redis_client is not None:
        # 使用 aclose() 而不是 close() 以避免弃用警告
        if aclose := getattr(async_redis_client, "aclose", None):
            await aclose()
        else:
            await async_redis_client.close()
        async_redis_client = None


MAXSIZE = 8

REDIS_URL = getenv("REDIS_URL", "redis://")
REDIS_FACTORY = lambda: Redis.from_url(REDIS_URL)  # noqa: E731
ASYNC_REDIS_FACTORY = lambda: AsyncRedis.from_url(REDIS_URL)  # noqa: E731
REDIS_CLUSTER_NODES = getenv("REDIS_CLUSTER_NODES")

# 解析 Redis 集群节点
CLUSTER_NODES: List[ClusterNode] = []
CLUSTER_CACHES: Dict[str, RedisFuncCache] = {}
CLUSTER_MULTI_CACHES: Dict[str, RedisFuncCache] = {}

if REDIS_CLUSTER_NODES:
    CLUSTER_NODES = [
        ClusterNode(cluster.split(":")[-2], int(cluster.split(":")[-1])) for cluster in REDIS_CLUSTER_NODES.split()
    ]
    REDIS_CLUSTER_FACTORY: Callable[[], RedisCluster] = lambda: RedisCluster(startup_nodes=CLUSTER_NODES)  # type: ignore[abstract]  # noqa: E731

    CLUSTER_CACHES = {
        "tlru": RedisFuncCache(__name__, LruTClusterPolicy(), factory=REDIS_CLUSTER_FACTORY, maxsize=MAXSIZE),
        "lru": RedisFuncCache(__name__, LruClusterPolicy(), factory=REDIS_CLUSTER_FACTORY, maxsize=MAXSIZE),
        "mru": RedisFuncCache(__name__, MruClusterPolicy(), factory=REDIS_CLUSTER_FACTORY, maxsize=MAXSIZE),
        "rr": RedisFuncCache(__name__, RrClusterPolicy(), factory=REDIS_CLUSTER_FACTORY, maxsize=MAXSIZE),
        "fifo": RedisFuncCache(__name__, FifoClusterPolicy(), factory=REDIS_CLUSTER_FACTORY, maxsize=MAXSIZE),
        "lfu": RedisFuncCache(__name__, LfuClusterPolicy(), factory=REDIS_CLUSTER_FACTORY, maxsize=MAXSIZE),
    }

    CLUSTER_MULTI_CACHES = {
        "tlru": RedisFuncCache(__name__, LruTClusterMultiplePolicy(), factory=REDIS_CLUSTER_FACTORY, maxsize=MAXSIZE),
        "lru": RedisFuncCache(__name__, LruClusterMultiplePolicy(), factory=REDIS_CLUSTER_FACTORY, maxsize=MAXSIZE),
        "mru": RedisFuncCache(__name__, MruClusterMultiplePolicy(), factory=REDIS_CLUSTER_FACTORY, maxsize=MAXSIZE),
        "rr": RedisFuncCache(__name__, RrClusterMultiplePolicy(), factory=REDIS_CLUSTER_FACTORY, maxsize=MAXSIZE),
        "fifo": RedisFuncCache(__name__, FifoClusterMultiplePolicy(), factory=REDIS_CLUSTER_FACTORY, maxsize=MAXSIZE),
        "lfu": RedisFuncCache(__name__, LfuClusterMultiplePolicy(), factory=REDIS_CLUSTER_FACTORY, maxsize=MAXSIZE),
    }


CACHES = {
    "tlru": RedisFuncCache(__name__, LruTPolicy(), factory=REDIS_FACTORY, maxsize=MAXSIZE),
    "lru": RedisFuncCache(__name__, LruPolicy(), factory=REDIS_FACTORY, maxsize=MAXSIZE),
    "mru": RedisFuncCache(__name__, MruPolicy(), factory=REDIS_FACTORY, maxsize=MAXSIZE),
    "rr": RedisFuncCache(__name__, RrPolicy(), factory=REDIS_FACTORY, maxsize=MAXSIZE),
    "fifo": RedisFuncCache(__name__, FifoPolicy(), factory=REDIS_FACTORY, maxsize=MAXSIZE),
    "lfu": RedisFuncCache(__name__, LfuPolicy(), factory=REDIS_FACTORY, maxsize=MAXSIZE),
}

MULTI_CACHES = {
    "tlru": RedisFuncCache(__name__, LruTMultiplePolicy(), factory=REDIS_FACTORY, maxsize=MAXSIZE),
    "lru": RedisFuncCache(__name__, LruMultiplePolicy(), factory=REDIS_FACTORY, maxsize=MAXSIZE),
    "mru": RedisFuncCache(__name__, MruMultiplePolicy(), factory=REDIS_FACTORY, maxsize=MAXSIZE),
    "rr": RedisFuncCache(__name__, RrMultiplePolicy(), factory=REDIS_FACTORY, maxsize=MAXSIZE),
    "fifo": RedisFuncCache(__name__, FifoMultiplePolicy(), factory=REDIS_FACTORY, maxsize=MAXSIZE),
    "lfu": RedisFuncCache(__name__, LfuMultiplePolicy(), factory=REDIS_FACTORY, maxsize=MAXSIZE),
}


ASYNC_CACHES = {
    "tlru": RedisFuncCache(__name__, LruTPolicy(), factory=ASYNC_REDIS_FACTORY, maxsize=MAXSIZE),
    "lru": RedisFuncCache(__name__, LruPolicy(), factory=ASYNC_REDIS_FACTORY, maxsize=MAXSIZE),
    "mru": RedisFuncCache(__name__, MruPolicy(), factory=ASYNC_REDIS_FACTORY, maxsize=MAXSIZE),
    "rr": RedisFuncCache(__name__, RrPolicy(), factory=ASYNC_REDIS_FACTORY, maxsize=MAXSIZE),
    "fifo": RedisFuncCache(__name__, FifoPolicy(), factory=ASYNC_REDIS_FACTORY, maxsize=MAXSIZE),
    "lfu": RedisFuncCache(__name__, LfuPolicy(), factory=ASYNC_REDIS_FACTORY, maxsize=MAXSIZE),
}


ASYNC_MULTI_CACHES = {
    "tlru": RedisFuncCache(__name__, LruTClusterMultiplePolicy(), factory=ASYNC_REDIS_FACTORY, maxsize=MAXSIZE),
    "lru": RedisFuncCache(__name__, LruClusterMultiplePolicy(), factory=ASYNC_REDIS_FACTORY, maxsize=MAXSIZE),
    "mru": RedisFuncCache(__name__, MruClusterMultiplePolicy(), factory=ASYNC_REDIS_FACTORY, maxsize=MAXSIZE),
    "rr": RedisFuncCache(__name__, RrClusterMultiplePolicy(), factory=ASYNC_REDIS_FACTORY, maxsize=MAXSIZE),
    "fifo": RedisFuncCache(__name__, FifoClusterMultiplePolicy(), factory=ASYNC_REDIS_FACTORY, maxsize=MAXSIZE),
    "lfu": RedisFuncCache(__name__, LfuClusterMultiplePolicy(), factory=ASYNC_REDIS_FACTORY, maxsize=MAXSIZE),
}


async def close_all_async_resources():
    """关闭所有异步资源，防止出现 'Event loop is closed' 错误"""
    try:
        # 关闭全局异步Redis客户端
        await close_async_redis_client()

        # 关闭所有异步缓存实例中的客户端连接
        tasks = []
        for cache in ASYNC_CACHES.values():
            try:
                if aclose := getattr(cache.client, "aclose", None):
                    tasks.append(aclose())
                elif hasattr(cache.client, "close"):
                    tasks.append(cache.client.close())
            except Exception:
                # 忽略单个客户端关闭过程中可能出现的异常
                pass

        for cache in ASYNC_MULTI_CACHES.values():
            try:
                if aclose := getattr(cache.client, "aclose", None):
                    tasks.append(aclose())
                elif hasattr(cache.client, "close"):
                    tasks.append(cache.client.close())
            except Exception:
                # 忽略单个客户端关闭过程中可能出现的异常
                pass

        if tasks:
            # 使用return_exceptions=True确保即使某些任务失败也不会影响其他任务
            await asyncio.gather(*tasks, return_exceptions=True)
    except Exception:
        # 忽略所有异常，确保不会因为清理过程中的错误导致测试失败
        pass


# 确保在模块被清理时也尝试关闭所有异步资源
atexit.register(lambda: asyncio.run(close_all_async_resources()) if asyncio.get_event_loop() else None)
