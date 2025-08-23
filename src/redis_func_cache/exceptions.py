"""
.. versionadded:: 0.5
"""

__all__ = ("BaseCacheError", "CacheMissError")


class BaseCacheError(Exception):
    pass


class CacheMissError(BaseCacheError):
    pass
