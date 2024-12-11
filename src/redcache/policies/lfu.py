from ..mixins.md5hash import Md5HashMixin
from .base import BaseSinglePolicy

__all__ = ["LfuPolicy"]


class LfuPolicy(Md5HashMixin, BaseSinglePolicy):
    """All functions are cached in a single sorted-set/hash-map pair of redis, with least frequently used eviction policy."""

    __name__ = "lfu"
    __scripts__ = "lfu_get.lua", "lfu_put.lua"
