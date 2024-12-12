from ..mixins.md5hash import Md5PickleMixin
from ..mixins.policies import LfuScriptsMixin
from .base import BaseClusterMultiplePolicy, BaseClusterSinglePolicy, BaseMultiplePolicy, BaseSinglePolicy

__all__ = ("LfuPolicy", "LfuMultiplePolicy", "LfuClusterPolicy", "LfuClusterMultiplePolicy")


class LfuPolicy(LfuScriptsMixin, Md5PickleMixin, BaseSinglePolicy):
    """All functions are cached in a single sorted-set/hash-map pair of redis, use least frequently used eviction policy."""

    __key__ = "lfu"


class LfuMultiplePolicy(LfuScriptsMixin, Md5PickleMixin, BaseMultiplePolicy):
    """Each function is cached in a single sorted-set/hash-map pair of redis, use least frequently used eviction policy."""

    __key__ = "lfu-m"


class LfuClusterPolicy(LfuScriptsMixin, Md5PickleMixin, BaseClusterSinglePolicy):
    """All functions are cached in a single sorted-set/hash-map pair of redis with cluster support, use least frequently used eviction policy."""

    __key__ = "lfu-c"


class LfuClusterMultiplePolicy(LfuScriptsMixin, Md5PickleMixin, BaseClusterMultiplePolicy):
    """Each function is cached in a single sorted-set/hash-map pair of redis with cluster support, use least frequently used eviction policy."""

    __key__ = "lfu-cm"
