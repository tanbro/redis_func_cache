import asyncio
from time import time

from redis.asyncio import Redis

from redis_func_cache import LruTPolicy, RedisFuncCache

# Create a redis client
redis_instance = Redis.from_url("redis://")

# Create an lru cache, it connects Redis by previous created redis client
lru_cache = RedisFuncCache(__name__, LruTPolicy(), redis_instance=redis_instance)


@lru_cache  # Decorate a function to cache its result
async def a_slow_func():
    await asyncio.sleep(10)  # Sleep to simulate a slow operation
    return "OK"


with asyncio.Runner() as runner:
    t = time()
    r = runner.run(a_slow_func())
    print(f"duration={time() - t}, {r=}")

    t = time()
    r = runner.run(a_slow_func())
    print(f"duration={time() - t}, {r=}")
