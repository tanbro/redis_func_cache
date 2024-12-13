from ..mixins.hash import PickleMd5Base64HashMixin
from ..mixins.policies import RrScriptsMixin
from .base import BaseClusterMultiplePolicy, BaseClusterSinglePolicy, BaseMultiplePolicy, BaseSinglePolicy

__all__ = ("RrPolicy", "RrMultiplePolicy", "RrClusterPolicy", "RrClusterMultiplePolicy")


class RrPolicy(RrScriptsMixin, PickleMd5Base64HashMixin, BaseSinglePolicy):
    """All decorated functions share the same key pair, use random replacement eviction policy."""

    __key__ = "rr"


class RrMultiplePolicy(RrScriptsMixin, PickleMd5Base64HashMixin, BaseMultiplePolicy):
    """Each decorated function of the policy has its own key pair, use random replacement eviction policy."""

    __key__ = "rr-m"


class RrClusterPolicy(RrScriptsMixin, PickleMd5Base64HashMixin, BaseClusterSinglePolicy):
    """All decorated functions share the same key pair, with cluster support, use random replacement eviction policy."""

    __key__ = "rr-c"


class RrClusterMultiplePolicy(RrScriptsMixin, PickleMd5Base64HashMixin, BaseClusterMultiplePolicy):
    """Each decorated function of the policy has its own key pair with cluster support, use random replacement eviction policy."""

    __key__ = "rr-cm"
