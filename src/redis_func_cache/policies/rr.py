"""Random replacement eviction cache policy."""

from typing import final

from ..mixins.hash import PickleMd5HashMixin
from ..mixins.scripts import RrScriptsMixin
from .base import BaseClusterMultiplePolicy, BaseClusterSinglePolicy, BaseMultiplePolicy, BaseSinglePolicy

__all__ = ("RrPolicy", "RrMultiplePolicy", "RrClusterPolicy", "RrClusterMultiplePolicy")


@final
class RrPolicy(RrScriptsMixin, PickleMd5HashMixin, BaseSinglePolicy):
    """
    Random replacement (RR) eviction policy, single key pair.

    .. inheritance-diagram:: RrPolicy
        :parts: 1

    All decorated functions share the same Redis key pair.
    """

    __key__ = "rr"


@final
class RrMultiplePolicy(RrScriptsMixin, PickleMd5HashMixin, BaseMultiplePolicy):
    """
    Random replacement (RR) eviction policy, multiple key pairs.

    .. inheritance-diagram:: RrMultiplePolicy
        :parts: 1

    Each decorated function has its own Redis key pair.
    """

    __key__ = "rr-m"


@final
class RrClusterPolicy(RrScriptsMixin, PickleMd5HashMixin, BaseClusterSinglePolicy):
    """
    Random replacement (RR) eviction policy with Redis cluster support, single key pair.

    .. inheritance-diagram:: RrClusterPolicy
        :parts: 1

    All decorated functions share the same Redis key pair.
    """

    __key__ = "rr-c"


@final
class RrClusterMultiplePolicy(RrScriptsMixin, PickleMd5HashMixin, BaseClusterMultiplePolicy):
    """
    Random replacement (RR) eviction policy with Redis cluster support, multiple key pairs.

    .. inheritance-diagram:: RrClusterMultiplePolicy
        :parts: 1

    Each decorated function has its own Redis key pair.
    """

    __key__ = "rr-cm"
