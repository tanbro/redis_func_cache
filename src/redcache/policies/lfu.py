from ..mixins.md5hash import Md5PickleMixin
from ..mixins.policies import LfuScriptsMixin
from .base import BaseSinglePolicy

__all__ = ["LfuPolicy"]


class LfuPolicy(LfuScriptsMixin, Md5PickleMixin, BaseSinglePolicy):
    """All functions are cached in a single sorted-set/hash-map pair of redis, with least frequently used eviction policy."""

    __key__ = "lfu"
    __scripts__ = "lfu_get.lua", "lfu_put.lua"
