"""LFU policy."""

from ..mixins.hash import PickleMd5HashMixin
from ..mixins.scripts import LfuScriptsMixin
from .base import BaseClusterMultiplePolicy, BaseClusterSinglePolicy, BaseMultiplePolicy, BaseSinglePolicy

__all__ = ("LfuPolicy", "LfuMultiplePolicy", "LfuClusterPolicy", "LfuClusterMultiplePolicy")


class LfuPolicy(LfuScriptsMixin, PickleMd5HashMixin, BaseSinglePolicy):
    """
    LFU eviction policy, single key pair.

    All decorated functions share the same Redis key pair.
    """

    __key__ = "lfu"


class LfuMultiplePolicy(LfuScriptsMixin, PickleMd5HashMixin, BaseMultiplePolicy):
    """
    LFU eviction policy, multiple key pairs.

    Each decorated function has its own Redis key pair.
    """

    __key__ = "lfu-m"


class LfuClusterPolicy(LfuScriptsMixin, PickleMd5HashMixin, BaseClusterSinglePolicy):
    """
    LFU eviction policy with Redis cluster support, single key pair.

    All decorated functions share the same Redis key pair.
    """

    __key__ = "lfu-c"


class LfuClusterMultiplePolicy(LfuScriptsMixin, PickleMd5HashMixin, BaseClusterMultiplePolicy):
    """
    LFU eviction policy with Redis cluster support, multiple key pairs.

    Each decorated function has its own Redis key pair.
    """

    __key__ = "lfu-cm"
