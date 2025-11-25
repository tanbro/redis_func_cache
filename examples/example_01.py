from time import sleep, time

from redis import Redis

from redis_func_cache import LruTPolicy, RedisFuncCache

# Create a redis client
redis_client = Redis.from_url("redis://")

# Create an lru cache, it connects Redis by previous created redis client
lru_cache = RedisFuncCache(__name__, LruTPolicy(), redis_client)


@lru_cache  # Decorate a function to cache its result
def a_slow_func():
    sleep(10)  # Sleep to simulate a slow operation
    return "OK"


t = time()
r = a_slow_func()
print(f"duration={time() - t}, {r=}")

t = time()
r = a_slow_func()
print(f"duration={time() - t}, {r=}")
