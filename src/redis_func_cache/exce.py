__all__ = ("RedisFuncCacheException", "CacheMissError")


class RedisFuncCacheException(Exception):
    pass


class CacheMissError(RedisFuncCacheException):
    """Raised when a cache miss occurs in GET_ONLY mode."""

    pass
