"""Random replacement cache policy."""

from ..mixins.hash import PickleMd5HashMixin
from ..mixins.scripts import RrScriptsMixin
from .base import BaseClusterMultiplePolicy, BaseClusterSinglePolicy, BaseMultiplePolicy, BaseSinglePolicy

__all__ = ("RrPolicy", "RrMultiplePolicy", "RrClusterPolicy", "RrClusterMultiplePolicy")


class RrPolicy(RrScriptsMixin, PickleMd5HashMixin, BaseSinglePolicy):
    """
    Random replacement (RR) eviction policy, single key pair.

    All decorated functions share the same Redis key pair.
    """

    __key__ = "rr"


class RrMultiplePolicy(RrScriptsMixin, PickleMd5HashMixin, BaseMultiplePolicy):
    """
    Random replacement (RR) eviction policy, multiple key pairs.

    Each decorated function has its own Redis key pair.
    """

    __key__ = "rr-m"


class RrClusterPolicy(RrScriptsMixin, PickleMd5HashMixin, BaseClusterSinglePolicy):
    """
    Random replacement (RR) eviction policy with Redis cluster support, single key pair.

    All decorated functions share the same Redis key pair.
    """

    __key__ = "rr-c"


class RrClusterMultiplePolicy(RrScriptsMixin, PickleMd5HashMixin, BaseClusterMultiplePolicy):
    """
    Random replacement (RR) eviction policy with Redis cluster support, multiple key pairs.

    Each decorated function has its own Redis key pair.
    """

    __key__ = "rr-cm"
