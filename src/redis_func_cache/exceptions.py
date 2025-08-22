__all__ = ("BaseCacheError", "CacheMissError")


class BaseCacheError(Exception):
    pass


class CacheMissError(BaseCacheError):
    pass
