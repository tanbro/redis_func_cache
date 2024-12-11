from ..mixins import Md5HashMixin
from .abstract import AbstractSinglePolicy

__all__ = ["LruPolicy"]


class LruPolicy(Md5HashMixin, AbstractSinglePolicy):
    """All functions are cached in a sorted-set/hash-map pair of redis, with Least Recently Used eviction policy."""

    __name__ = "lru"
    __scripts__ = "lru_get.lua", "lru_put.lua"
