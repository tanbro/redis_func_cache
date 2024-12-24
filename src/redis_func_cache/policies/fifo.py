"""FIFO policies"""

from ..mixins.hash import PickleMd5HashMixin
from ..mixins.policies import FifoScriptsMixin, FifoTScriptsMixin
from .base import BaseClusterMultiplePolicy, BaseClusterSinglePolicy, BaseMultiplePolicy, BaseSinglePolicy

__all__ = (
    "FifoPolicy",
    "FifoClusterPolicy",
    "FifoClusterMultiplePolicy",
    "FifoMultiplePolicy",
    "FifoTPolicy",
    "FifoTClusterPolicy",
    "FifoTClusterMultiplePolicy",
    "FifoTMultiplePolicy",
)


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


class FifoTPolicy(FifoTScriptsMixin, PickleMd5HashMixin, BaseSinglePolicy):
    """
    .. inheritance-diagram:: FifoTPolicy

    All decorated functions share the same key pair, use First In First Out eviction policy.
    """

    __key__ = "fifo_t"


class FifoTMultiplePolicy(FifoTScriptsMixin, PickleMd5HashMixin, BaseMultiplePolicy):
    """
    .. inheritance-diagram:: FifoTMultiplePolicy

    Each decorated function has its own key pair, use First In First Out eviction policy.
    """

    __key__ = "fifo_t-m"


class FifoTClusterPolicy(FifoTScriptsMixin, PickleMd5HashMixin, BaseClusterSinglePolicy):
    """
    .. inheritance-diagram:: FifoTClusterPolicy

    All decorated functions share the same key pair, with cluster support, use First In First Out eviction policy.
    """

    __key__ = "fifo_t-c"


class FifoTClusterMultiplePolicy(FifoTScriptsMixin, PickleMd5HashMixin, BaseClusterMultiplePolicy):
    """
    .. inheritance-diagram:: FifoTClusterMultiplePolicy

    Each decorated function has its own key pair, with cluster support, use First In First Out eviction policy.
    """

    __key__ = "fifo_t-cm"
