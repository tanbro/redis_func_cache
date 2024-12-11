from ..mixins import Md5HashMixin
from .single import SinglePolicy

__all__ = ["RandPolicy"]


class RandPolicy(Md5HashMixin, SinglePolicy):
    """All functions are cached in a sorted-set/hash-map pair of redis, with random eviction policy."""

    __name__ = "rand"
    __scripts__ = "rand_get.lua", "rand_put.lua"
