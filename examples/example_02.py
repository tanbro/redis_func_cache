import asyncio
from time import time

import redis.asyncio as aioredis

from redis_func_cache import LruTPolicy, RedisFuncCache

# Create a redis client factory
factory = lambda: aioredis.Redis.from_pool(aioredis.ConnectionPool.from_url("redis://"))

# Create an lru cache, it connects Redis by previous created redis client
lru_cache = RedisFuncCache(__name__, LruTPolicy, factory=factory)


@lru_cache  # Decorate a function to cache its result
async def a_slow_func():
    await asyncio.sleep(10)  # Sleep to simulate a slow operation
    return "OK"


t = time()
r = asyncio.run(a_slow_func())
print(f"duration={time() - t}, {r=}")

t = time()
r = asyncio.run(a_slow_func())
print(f"duration={time() - t}, {r=}")
