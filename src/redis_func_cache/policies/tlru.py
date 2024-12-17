from ..mixins.hash import PickleMd5HashMixin
from ..mixins.policies import TLruScriptsMixin
from .base import BaseClusterMultiplePolicy, BaseClusterSinglePolicy, BaseMultiplePolicy, BaseSinglePolicy

__all__ = ("TLruPolicy", "TLruMultiplePolicy", "TLruClusterPolicy", "TLruClusterMultiplePolicy")


class TLruPolicy(TLruScriptsMixin, PickleMd5HashMixin, BaseSinglePolicy):
    """All decorated functions share the same key pair, use time based pseudo Least Recently Used eviction policy.

    .. inheritance-diagram:: TLruPolicy
    """

    __key__ = "tlru"


class TLruMultiplePolicy(TLruScriptsMixin, PickleMd5HashMixin, BaseMultiplePolicy):
    """Each decorated function of the policy has its own key pair, use time based pseudo Least Recently Used eviction policy.

    .. inheritance-diagram:: TLruMultiplePolicy
    """

    __key__ = "tlru-m"


class TLruClusterPolicy(TLruScriptsMixin, PickleMd5HashMixin, BaseClusterSinglePolicy):
    """All decorated functions share the same key pair, with cluster support, use time based pseudo Least Recently Used eviction policy.

    .. inheritance-diagram:: TLruClusterPolicy
    """

    __key__ = "tlru-c"


class TLruClusterMultiplePolicy(TLruScriptsMixin, PickleMd5HashMixin, BaseClusterMultiplePolicy):
    """Each decorated function of the policy has its own key pair, with cluster support, use time based pseudo Least Recently Used eviction policy.

    .. inheritance-diagram:: TLruClusterMultiplePolicy
    """

    __key__ = "tlru-cm"
