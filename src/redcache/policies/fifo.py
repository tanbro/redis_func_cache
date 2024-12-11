from ..mixins import Md5HashMixin
from .abstract import AbstractSinglePolicy

__all__ = ["FifoPolicy"]


class FifoPolicy(Md5HashMixin, AbstractSinglePolicy):
    """All functions are cached in a sorted-set/hash-map pair of redis, with fist in first out eviction policy."""

    __name__ = "fifo"
    __scripts__ = "fifo_get.lua", "fifo_put.lua"
