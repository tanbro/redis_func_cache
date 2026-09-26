from __future__ import annotations

import asyncio
import atexit
import weakref
from collections.abc import Callable, Coroutine
from os import getenv
from typing import TYPE_CHECKING
from warnings import warn

from redis import Redis
from redis.asyncio import ConnectionPool as AsyncConnectionPool
from redis.asyncio import Redis as AsyncRedis
from redis.asyncio.cluster import ClusterNode as AsyncClusterNode
from redis.cluster import ClusterNode, RedisCluster
from redis.connection import ConnectionPool

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
from redis_func_cache.typing import is_redis_async_client

if TYPE_CHECKING:
    from redis_func_cache.policies import Policy
    from redis_func_cache.typing import RedisAsyncClientT, RedisSyncClientT

try:
    from dotenv import load_dotenv
except ImportError as err:
    warn(f"{err} is not installed.")
else:
    load_dotenv()


redis_pool: ConnectionPool | None = None
redis_client: Redis | None = None
async_redis_client: AsyncRedis | None = None


def redis_factory(**kwargs):
    """返回包在进程级共享连接池之上的客户端。

    与 cache.py 文档一致：factory 每次访问都会被调用，应当返回共享池上的
    轻量包装，而不是每次新建连接池。
    """
    global redis_pool
    if redis_pool is None:
        redis_pool = ConnectionPool.from_url(REDIS_URL)
    return Redis(connection_pool=redis_pool)


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
REDIS_POOL = ConnectionPool.from_url(REDIS_URL)
REDIS_FACTORY = lambda: Redis(connection_pool=REDIS_POOL)

# redis.asyncio 连接绑定创建时的事件循环，池不能跨 loop 复用
# （pytest-asyncio 每测试独立 loop）；但同一 loop 内应当像生产环境一样共享池，
# 而不是 factory 每次访问都新建。因此按运行中的 loop 缓存池，loop 结束后清理。
async_loop_pools: dict[int, tuple] = {}


def async_redis_pool_factory(**kwargs):
    """返回包在当前事件循环共享连接池之上的异步客户端。

    与同步侧和 cache.py 文档一致：factory 每次访问都会被调用，应当返回共享
    池上的轻量包装；池本身按事件循环隔离。
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # 无事件循环的上下文（如类型守卫测试）只构造客户端、不发起请求，一次性新建即可
        return AsyncRedis.from_url(REDIS_URL)
    entry = async_loop_pools.get(id(loop))
    if entry is not None and entry[0]() is loop:
        return AsyncRedis(connection_pool=entry[1])
    for key, (ref, _) in list(async_loop_pools.items()):
        pooled_loop = ref()
        if pooled_loop is None or pooled_loop.is_closed():
            del async_loop_pools[key]
    pool = AsyncConnectionPool.from_url(REDIS_URL)
    async_loop_pools[id(loop)] = (weakref.ref(loop), pool)
    return AsyncRedis(connection_pool=pool)


ASYNC_REDIS_FACTORY = async_redis_pool_factory
REDIS_CLUSTER_NODES = getenv("REDIS_CLUSTER_NODES")

# 解析 Redis 集群节点
CLUSTER_NODES: list[ClusterNode] = []
ASYNC_CLUSTER_NODES: list[AsyncClusterNode] = []
CLUSTER_CACHES: dict[str, RedisFuncCache[RedisSyncClientT, Policy]] = {}
CLUSTER_MULTI_CACHES: dict[str, RedisFuncCache[RedisSyncClientT, Policy]] = {}

if REDIS_CLUSTER_NODES:
    CLUSTER_NODES = [
        ClusterNode(cluster.split(":")[-2], int(cluster.split(":")[-1])) for cluster in REDIS_CLUSTER_NODES.split()
    ]
    ASYNC_CLUSTER_NODES = [
        AsyncClusterNode(cluster.split(":")[-2], int(cluster.split(":")[-1])) for cluster in REDIS_CLUSTER_NODES.split()
    ]

    cluster_redis_client: RedisCluster | None = None

    def cluster_redis_factory(**kwargs):
        """集群客户端按进程单例复用：拓扑发现开销大，不宜每次访问重建。"""
        global cluster_redis_client
        if cluster_redis_client is None:
            cluster_redis_client = RedisCluster(startup_nodes=CLUSTER_NODES)  # type: ignore[abstract,arg-type]
        return cluster_redis_client

    REDIS_CLUSTER_FACTORY: Callable[[], RedisCluster] = cluster_redis_factory

    CLUSTER_CACHES = {
        "tlru": RedisFuncCache(__name__, LruTClusterPolicy, factory=REDIS_CLUSTER_FACTORY, maxsize=MAXSIZE),
        "lru": RedisFuncCache(__name__, LruClusterPolicy, factory=REDIS_CLUSTER_FACTORY, maxsize=MAXSIZE),
        "mru": RedisFuncCache(__name__, MruClusterPolicy, factory=REDIS_CLUSTER_FACTORY, maxsize=MAXSIZE),
        "rr": RedisFuncCache(__name__, RrClusterPolicy, factory=REDIS_CLUSTER_FACTORY, maxsize=MAXSIZE),
        "fifo": RedisFuncCache(__name__, FifoClusterPolicy, factory=REDIS_CLUSTER_FACTORY, maxsize=MAXSIZE),
        "lfu": RedisFuncCache(__name__, LfuClusterPolicy, factory=REDIS_CLUSTER_FACTORY, maxsize=MAXSIZE),
    }

    CLUSTER_MULTI_CACHES = {
        "tlru": RedisFuncCache(__name__, LruTClusterMultiplePolicy, factory=REDIS_CLUSTER_FACTORY, maxsize=MAXSIZE),
        "lru": RedisFuncCache(__name__, LruClusterMultiplePolicy, factory=REDIS_CLUSTER_FACTORY, maxsize=MAXSIZE),
        "mru": RedisFuncCache(__name__, MruClusterMultiplePolicy, factory=REDIS_CLUSTER_FACTORY, maxsize=MAXSIZE),
        "rr": RedisFuncCache(__name__, RrClusterMultiplePolicy, factory=REDIS_CLUSTER_FACTORY, maxsize=MAXSIZE),
        "fifo": RedisFuncCache(__name__, FifoClusterMultiplePolicy, factory=REDIS_CLUSTER_FACTORY, maxsize=MAXSIZE),
        "lfu": RedisFuncCache(__name__, LfuClusterMultiplePolicy, factory=REDIS_CLUSTER_FACTORY, maxsize=MAXSIZE),
    }


CACHES: dict[str, RedisFuncCache[RedisSyncClientT, Policy]] = {
    "tlru": RedisFuncCache(__name__, LruTPolicy, factory=REDIS_FACTORY, maxsize=MAXSIZE),
    "lru": RedisFuncCache(__name__, LruPolicy, factory=REDIS_FACTORY, maxsize=MAXSIZE),
    "mru": RedisFuncCache(__name__, MruPolicy, factory=REDIS_FACTORY, maxsize=MAXSIZE),
    "rr": RedisFuncCache(__name__, RrPolicy, factory=REDIS_FACTORY, maxsize=MAXSIZE),
    "fifo": RedisFuncCache(__name__, FifoPolicy, factory=REDIS_FACTORY, maxsize=MAXSIZE),
    "lfu": RedisFuncCache(__name__, LfuPolicy, factory=REDIS_FACTORY, maxsize=MAXSIZE),
}

MULTI_CACHES: dict[str, RedisFuncCache[RedisSyncClientT, Policy]] = {
    "tlru": RedisFuncCache(__name__, LruTMultiplePolicy, factory=REDIS_FACTORY, maxsize=MAXSIZE),
    "lru": RedisFuncCache(__name__, LruMultiplePolicy, factory=REDIS_FACTORY, maxsize=MAXSIZE),
    "mru": RedisFuncCache(__name__, MruMultiplePolicy, factory=REDIS_FACTORY, maxsize=MAXSIZE),
    "rr": RedisFuncCache(__name__, RrMultiplePolicy, factory=REDIS_FACTORY, maxsize=MAXSIZE),
    "fifo": RedisFuncCache(__name__, FifoMultiplePolicy, factory=REDIS_FACTORY, maxsize=MAXSIZE),
    "lfu": RedisFuncCache(__name__, LfuMultiplePolicy, factory=REDIS_FACTORY, maxsize=MAXSIZE),
}


ASYNC_CACHES: dict[str, RedisFuncCache[RedisAsyncClientT, Policy]] = {
    "tlru": RedisFuncCache(__name__, LruTPolicy, factory=ASYNC_REDIS_FACTORY, maxsize=MAXSIZE),
    "lru": RedisFuncCache(__name__, LruPolicy, factory=ASYNC_REDIS_FACTORY, maxsize=MAXSIZE),
    "mru": RedisFuncCache(__name__, MruPolicy, factory=ASYNC_REDIS_FACTORY, maxsize=MAXSIZE),
    "rr": RedisFuncCache(__name__, RrPolicy, factory=ASYNC_REDIS_FACTORY, maxsize=MAXSIZE),
    "fifo": RedisFuncCache(__name__, FifoPolicy, factory=ASYNC_REDIS_FACTORY, maxsize=MAXSIZE),
    "lfu": RedisFuncCache(__name__, LfuPolicy, factory=ASYNC_REDIS_FACTORY, maxsize=MAXSIZE),
}


ASYNC_MULTI_CACHES: dict[str, RedisFuncCache[RedisAsyncClientT, Policy]] = {
    "tlru": RedisFuncCache(__name__, LruTClusterMultiplePolicy, factory=ASYNC_REDIS_FACTORY, maxsize=MAXSIZE),
    "lru": RedisFuncCache(__name__, LruClusterMultiplePolicy, factory=ASYNC_REDIS_FACTORY, maxsize=MAXSIZE),
    "mru": RedisFuncCache(__name__, MruClusterMultiplePolicy, factory=ASYNC_REDIS_FACTORY, maxsize=MAXSIZE),
    "rr": RedisFuncCache(__name__, RrClusterMultiplePolicy, factory=ASYNC_REDIS_FACTORY, maxsize=MAXSIZE),
    "fifo": RedisFuncCache(__name__, FifoClusterMultiplePolicy, factory=ASYNC_REDIS_FACTORY, maxsize=MAXSIZE),
    "lfu": RedisFuncCache(__name__, LfuClusterMultiplePolicy, factory=ASYNC_REDIS_FACTORY, maxsize=MAXSIZE),
}


async def close_all_async_resources():
    """关闭所有异步资源，防止出现 'Event loop is closed' 错误"""
    try:
        # 关闭全局异步Redis客户端
        await close_async_redis_client()

        # 关闭所有异步缓存实例中的客户端连接
        tasks: list[Coroutine] = []  # type:ignore[annotation-unchecked]
        for cache in ASYNC_CACHES.values():
            client = cache.get_redis_client()
            assert is_redis_async_client(client)
            try:
                if aclose := getattr(client, "aclose", None):
                    tasks.append(aclose())
                elif hasattr(client, "close"):
                    tasks.append(client.close())
            except Exception:  # noqa: BLE001, S110
                # 忽略单个客户端关闭过程中可能出现的异常
                pass

        for cache in ASYNC_MULTI_CACHES.values():
            client = cache.get_redis_client()
            assert is_redis_async_client(client)
            try:
                if aclose := getattr(client, "aclose", None):
                    tasks.append(aclose())
                elif hasattr(client, "close"):
                    tasks.append(client.close())
            except Exception:  # noqa: BLE001, S110
                # 忽略单个客户端关闭过程中可能出现的异常
                pass

        if tasks:
            # 使用return_exceptions=True确保即使某些任务失败也不会影响其他任务
            await asyncio.gather(*tasks, return_exceptions=True)
    except Exception:  # noqa: BLE001, S110
        # 忽略所有异常，确保不会因为清理过程中的错误导致测试失败
        pass


# 确保在模块被清理时也尝试关闭所有异步资源
try:
    asyncio.get_event_loop()
except RuntimeError as err:
    warn(f"{err}")
else:
    atexit.register(lambda: asyncio.run(close_all_async_resources()))
