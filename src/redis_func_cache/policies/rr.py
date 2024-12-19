"""Random replacement cache policy."""

from ..mixins.hash import PickleMd5HashMixin
from ..mixins.policies import RrScriptsMixin
from .base import BaseClusterMultiplePolicy, BaseClusterSinglePolicy, BaseMultiplePolicy, BaseSinglePolicy

__all__ = ("RrPolicy", "RrMultiplePolicy", "RrClusterPolicy", "RrClusterMultiplePolicy")


class RrPolicy(RrScriptsMixin, PickleMd5HashMixin, BaseSinglePolicy):
    """
    .. inheritance-diagram:: RrPolicy

    All decorated functions share the same key pair, use random replacement eviction policy.
    """

    __key__ = "rr"


class RrMultiplePolicy(RrScriptsMixin, PickleMd5HashMixin, BaseMultiplePolicy):
    """
    .. inheritance-diagram:: RrMultiplePolicy

    Each decorated function of the policy has its own key pair, use random replacement eviction policy.
    """

    __key__ = "rr-m"


class RrClusterPolicy(RrScriptsMixin, PickleMd5HashMixin, BaseClusterSinglePolicy):
    """
    .. inheritance-diagram:: RrClusterPolicy

    All decorated functions share the same key pair, with cluster support, use random replacement eviction policy.
    """

    __key__ = "rr-c"


class RrClusterMultiplePolicy(RrScriptsMixin, PickleMd5HashMixin, BaseClusterMultiplePolicy):
    """
    .. inheritance-diagram:: RrClusterMultiplePolicy

    Each decorated function of the policy has its own key pair with cluster support, use random replacement eviction policy.
    """

    __key__ = "rr-cm"
