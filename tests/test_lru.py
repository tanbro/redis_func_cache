from redis import Redis

from redcache import LruPolicy, RedCache

rc = Redis.from_url("redis://")

# lru_cache = RedCache(__name__, LruPolicy, redis_client=rc, maxsize=100, ttl=300)
lru_cache = RedCache(__name__, LruPolicy, redis_client=rc)


@lru_cache
def fib(n: int) -> int:
    return n if n < 2 else fib(n - 1) + fib(n - 2)

@lru_cache
def add(a: int, b: int):
    return a + b
