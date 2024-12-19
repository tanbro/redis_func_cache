"""FIFO policies"""

from ..mixins.hash import PickleMd5HashMixin
from ..mixins.policies import FifoScriptsMixin
from .base import BaseClusterMultiplePolicy, BaseClusterSinglePolicy, BaseMultiplePolicy, BaseSinglePolicy

__all__ = ("FifoPolicy", "FifoClusterPolicy", "FifoClusterMultiplePolicy", "FifoMultiplePolicy")


class FifoPolicy(FifoScriptsMixin, PickleMd5HashMixin, BaseSinglePolicy):
    """
    .. inheritance-diagram:: FifoPolicy

    All decorated functions share the same key pair, use First In First Out eviction policy.
    """

    __key__ = "fifo"


class FifoMultiplePolicy(FifoScriptsMixin, PickleMd5HashMixin, BaseMultiplePolicy):
    """
    .. inheritance-diagram:: FifoMultiplePolicy

    Each decorated function has its own key pair, use First In First Out eviction policy.
    """

    __key__ = "fifo-m"


class FifoClusterPolicy(FifoScriptsMixin, PickleMd5HashMixin, BaseClusterSinglePolicy):
    """
    .. inheritance-diagram:: FifoClusterPolicy

    All decorated functions share the same key pair, with cluster support, use First In First Out eviction policy.
    """

    __key__ = "fifo-c"


class FifoClusterMultiplePolicy(FifoScriptsMixin, PickleMd5HashMixin, BaseClusterMultiplePolicy):
    """
    .. inheritance-diagram:: FifoClusterMultiplePolicy

    Each decorated function has its own key pair, with cluster support, use First In First Out eviction policy.
    """

    __key__ = "fifo-cm"
