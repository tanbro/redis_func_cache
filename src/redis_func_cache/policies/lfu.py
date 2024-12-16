from ..mixins.hash import PickleMd5HashMixin
from ..mixins.policies import LfuScriptsMixin
from .base import BaseClusterMultiplePolicy, BaseClusterSinglePolicy, BaseMultiplePolicy, BaseSinglePolicy

__all__ = ("LfuPolicy", "LfuMultiplePolicy", "LfuClusterPolicy", "LfuClusterMultiplePolicy")


class LfuPolicy(LfuScriptsMixin, PickleMd5HashMixin, BaseSinglePolicy):
    """All functions are cached in a single sorted-set/hash-map pair of redis, use least frequently used eviction policy."""

    __key__ = "lfu"


class LfuMultiplePolicy(LfuScriptsMixin, PickleMd5HashMixin, BaseMultiplePolicy):
    """Each function is cached in a single sorted-set/hash-map pair of redis, use least frequently used eviction policy."""

    __key__ = "lfu-m"


class LfuClusterPolicy(LfuScriptsMixin, PickleMd5HashMixin, BaseClusterSinglePolicy):
    """All functions are cached in a single sorted-set/hash-map pair of redis with cluster support, use least frequently used eviction policy."""

    __key__ = "lfu-c"


class LfuClusterMultiplePolicy(LfuScriptsMixin, PickleMd5HashMixin, BaseClusterMultiplePolicy):
    """Each function is cached in a single sorted-set/hash-map pair of redis with cluster support, use least frequently used eviction policy."""

    __key__ = "lfu-cm"
