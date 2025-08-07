import asyncio
import atexit
from os import getenv
from typing import Optional
from warnings import warn

from redis import Redis
from redis.asyncio import Redis as AsyncRedis

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
from redis_func_cache.policies.fifo import FifoMultiplePolicy
from redis_func_cache.policies.lfu import LfuMultiplePolicy
from redis_func_cache.policies.lru import LruMultiplePolicy, LruTMultiplePolicy
from redis_func_cache.policies.mru import MruMultiplePolicy
from redis_func_cache.policies.rr import RrMultiplePolicy

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
        await async_redis_client.close()
        async_redis_client = None


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

MULTI_CACHES = {
    "tlru": RedisFuncCache(__name__, LruTMultiplePolicy, client=REDIS_FACTORY, maxsize=MAXSIZE),
    "lru": RedisFuncCache(__name__, LruMultiplePolicy, client=REDIS_FACTORY, maxsize=MAXSIZE),
    "mru": RedisFuncCache(__name__, MruMultiplePolicy, client=REDIS_FACTORY, maxsize=MAXSIZE),
    "rr": RedisFuncCache(__name__, RrMultiplePolicy, client=REDIS_FACTORY, maxsize=MAXSIZE),
    "fifo": RedisFuncCache(__name__, FifoMultiplePolicy, client=REDIS_FACTORY, maxsize=MAXSIZE),
    "lfu": RedisFuncCache(__name__, LfuMultiplePolicy, client=REDIS_FACTORY, maxsize=MAXSIZE),
}


ASYNC_CACHES = {
    "tlru": RedisFuncCache(__name__, LruTPolicy, client=ASYNC_REDIS_FACTORY, maxsize=MAXSIZE),
    "lru": RedisFuncCache(__name__, LruPolicy, client=ASYNC_REDIS_FACTORY, maxsize=MAXSIZE),
    "mru": RedisFuncCache(__name__, MruPolicy, client=ASYNC_REDIS_FACTORY, maxsize=MAXSIZE),
    "rr": RedisFuncCache(__name__, RrPolicy, client=ASYNC_REDIS_FACTORY, maxsize=MAXSIZE),
    "fifo": RedisFuncCache(__name__, FifoPolicy, client=ASYNC_REDIS_FACTORY, maxsize=MAXSIZE),
    "lfu": RedisFuncCache(__name__, LfuPolicy, client=ASYNC_REDIS_FACTORY, maxsize=MAXSIZE),
}


ASYNC_MULTI_CACHES = {
    "tlru": RedisFuncCache(__name__, LruTClusterMultiplePolicy, client=ASYNC_REDIS_FACTORY, maxsize=MAXSIZE),
    "lru": RedisFuncCache(__name__, LruClusterMultiplePolicy, client=ASYNC_REDIS_FACTORY, maxsize=MAXSIZE),
    "mru": RedisFuncCache(__name__, MruClusterMultiplePolicy, client=ASYNC_REDIS_FACTORY, maxsize=MAXSIZE),
    "rr": RedisFuncCache(__name__, RrClusterMultiplePolicy, client=ASYNC_REDIS_FACTORY, maxsize=MAXSIZE),
    "fifo": RedisFuncCache(__name__, FifoClusterMultiplePolicy, client=ASYNC_REDIS_FACTORY, maxsize=MAXSIZE),
    "lfu": RedisFuncCache(__name__, LfuClusterMultiplePolicy, client=ASYNC_REDIS_FACTORY, maxsize=MAXSIZE),
}


async def close_all_async_resources():
    """关闭所有异步资源，防止出现 'Event loop is closed' 错误"""
    # 关闭全局异步Redis客户端
    await close_async_redis_client()

    # 关闭所有异步缓存实例中的客户端连接
    for cache in ASYNC_CACHES.values():
        if hasattr(cache.client, "close"):
            try:
                await cache.client.close()
            except RuntimeError:
                # 如果事件循环已关闭，忽略错误
                pass

    for cache in ASYNC_MULTI_CACHES.values():
        if hasattr(cache.client, "close"):
            try:
                await cache.client.close()
            except RuntimeError:
                # 如果事件循环已关闭，忽略错误
                pass


def _cleanup_async_resources():
    """在程序退出时清理异步资源"""
    try:
        # 获取当前事件循环
        loop = asyncio.get_event_loop()
        # 如果事件循环还在运行，则执行清理
        if loop.is_running():
            loop.create_task(close_all_async_resources())
        else:
            # 否则直接运行直到完成
            loop.run_until_complete(close_all_async_resources())
    except RuntimeError:
        # 如果没有事件循环或者事件循环已关闭，忽略错误
        pass


# 在程序退出时注册清理函数
atexit.register(_cleanup_async_resources)
