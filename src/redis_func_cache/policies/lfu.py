"""LFU policy."""

from ..mixins.hash import PickleMd5HashMixin
from ..mixins.policies import LfuScriptsMixin
from .base import BaseClusterMultiplePolicy, BaseClusterSinglePolicy, BaseMultiplePolicy, BaseSinglePolicy

__all__ = ("LfuPolicy", "LfuMultiplePolicy", "LfuClusterPolicy", "LfuClusterMultiplePolicy")


class LfuPolicy(LfuScriptsMixin, PickleMd5HashMixin, BaseSinglePolicy):
    """
    .. inheritance-diagram:: LfuPolicy

    All decorated functions share the same key pair, use least frequently used eviction policy.
    """

    __key__ = "lfu"


class LfuMultiplePolicy(LfuScriptsMixin, PickleMd5HashMixin, BaseMultiplePolicy):
    """
    .. inheritance-diagram:: LfuMultiplePolicy

    Each function is cached in a standalone sorted-set/hash-map pair of redis, use least frequently used eviction policy.
    """

    __key__ = "lfu-m"


class LfuClusterPolicy(LfuScriptsMixin, PickleMd5HashMixin, BaseClusterSinglePolicy):
    """
    .. inheritance-diagram:: LfuClusterPolicy

    All functions are cached in a single sorted-set/hash-map pair of redis with cluster support, use least frequently used eviction policy.
    """

    __key__ = "lfu-c"


class LfuClusterMultiplePolicy(LfuScriptsMixin, PickleMd5HashMixin, BaseClusterMultiplePolicy):
    """
    .. inheritance-diagram:: LfuClusterMultiplePolicy

    Each function is cached in a single sorted-set/hash-map pair of redis with cluster support, use least frequently used eviction policy.
    """

    __key__ = "lfu-cm"
