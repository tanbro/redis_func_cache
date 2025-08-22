__all__ = ("RedisFuncCacheException", "CacheMissError")


class RedisFuncCacheException(Exception):
    pass


class CacheMissError(RedisFuncCacheException):
    pass
