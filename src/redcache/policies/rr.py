from ..mixins.md5hash import Md5PickleMixin
from ..mixins.policies import RrScriptsMixin
from .base import BaseClusterMultiplePolicy, BaseClusterSinglePolicy, BaseMultiplePolicy, BaseSinglePolicy

__all__ = ("RrPolicy", "RrMultiplePolicy", "RrClusterPolicy", "RrClusterMultiplePolicy")


class RrPolicy(RrScriptsMixin, Md5PickleMixin, BaseSinglePolicy):
    """All decorated functions share the same key pair, use random replacement eviction policy."""

    __name__ = "rr"


class RrMultiplePolicy(RrScriptsMixin, Md5PickleMixin, BaseMultiplePolicy):
    """Each decorated function of the policy has its own key pair, use random replacement eviction policy."""

    __name__ = "rr-m"


class RrClusterPolicy(RrScriptsMixin, Md5PickleMixin, BaseClusterSinglePolicy):
    """All decorated functions share the same key pair, with cluster support, use random replacement eviction policy."""

    __name__ = "rr-c"


class RrClusterMultiplePolicy(RrScriptsMixin, Md5PickleMixin, BaseClusterMultiplePolicy):
    """Each decorated function of the policy has its own key pair with cluster support, use random replacement eviction policy."""

    __name__ = "rr-cm"
