"""FIFO policies"""

from ..mixins.hash import PickleMd5HashMixin
from ..mixins.policies import FifoScriptsMixin
from .base import BaseClusterMultiplePolicy, BaseClusterSinglePolicy, BaseMultiplePolicy, BaseSinglePolicy

__all__ = ("FifoPolicy", "FifoClusterPolicy", "FifoClusterMultiplePolicy", "FifoMultiplePolicy")


class FifoPolicy(FifoScriptsMixin, PickleMd5HashMixin, BaseSinglePolicy):
    """
    All decorated functions share the same key pair, use First In First Out eviction policy.

    .. inheritance-diagram:: FifoPolicy
    """

    __key__ = "fifo"


class FifoMultiplePolicy(FifoScriptsMixin, PickleMd5HashMixin, BaseMultiplePolicy):
    """
    Each decorated function has its own key pair, use First In First Out eviction policy.

    .. inheritance-diagram:: FifoMultiplePolicy
    """

    __key__ = "fifo-m"


class FifoClusterPolicy(FifoScriptsMixin, PickleMd5HashMixin, BaseClusterSinglePolicy):
    """
    All decorated functions share the same key pair, with cluster support, use First In First Out eviction policy.

    .. inheritance-diagram:: FifoClusterPolicy
    """

    __key__ = "fifo-c"


class FifoClusterMultiplePolicy(FifoScriptsMixin, PickleMd5HashMixin, BaseClusterMultiplePolicy):
    """
    Each decorated function has its own key pair, with cluster support, use First In First Out eviction policy.

    .. inheritance-diagram:: FifoClusterMultiplePolicy
    """

    __key__ = "fifo-cm"
