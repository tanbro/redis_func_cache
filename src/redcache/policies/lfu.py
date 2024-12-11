from ..mixins import Md5HashMixin
from .abstract import AbstractSinglePolicy

__all__ = ["LfuPolicy"]


class LfuPolicy(Md5HashMixin, AbstractSinglePolicy):
    """All functions are cached in a sorted-set/hash-map pair of redis, with least frequently used eviction policy."""

    __name__ = "lfu"
    __scripts__ = "lfu_get.lua", "lfu_put.lua"
