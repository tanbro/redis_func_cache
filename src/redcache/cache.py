from redis import Redis


class RedCache:
    def __init__(self, redis_client: Redis):
        self._redis_client = redis_client

    @property
    def redis_client(self):
        return self._redis_client
