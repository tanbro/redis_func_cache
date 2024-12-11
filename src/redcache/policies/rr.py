from ..mixins import Md5HashMixin
from .abstract import AbstractSinglePolicy

__all__ = ["RrPolicy"]


class RrPolicy(Md5HashMixin, AbstractSinglePolicy):
    """All functions are cached in a sorted-set/hash-map pair of redis, with random replacement eviction policy."""

    __name__ = "rr"
    __scripts__ = "rr_get.lua", "rr_put.lua"
