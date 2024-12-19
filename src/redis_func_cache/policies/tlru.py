from ..mixins.hash import PickleMd5HashMixin
from ..mixins.policies import TLruScriptsMixin
from .base import BaseClusterMultiplePolicy, BaseClusterSinglePolicy, BaseMultiplePolicy, BaseSinglePolicy

__all__ = ("TLruPolicy", "TLruMultiplePolicy", "TLruClusterPolicy", "TLruClusterMultiplePolicy")


class TLruPolicy(TLruScriptsMixin, PickleMd5HashMixin, BaseSinglePolicy):
    """
    .. inheritance-diagram:: TLruPolicy

    All decorated functions share the same key pair, use time based pseudo Least Recently Used eviction policy.
    """

    __key__ = "tlru"


class TLruMultiplePolicy(TLruScriptsMixin, PickleMd5HashMixin, BaseMultiplePolicy):
    """
    .. inheritance-diagram:: TLruMultiplePolicy

    Each decorated function of the policy has its own key pair, use time based pseudo Least Recently Used eviction policy.
    """

    __key__ = "tlru-m"


class TLruClusterPolicy(TLruScriptsMixin, PickleMd5HashMixin, BaseClusterSinglePolicy):
    """
    .. inheritance-diagram:: TLruClusterPolicy

    All decorated functions share the same key pair, with cluster support, use time based pseudo Least Recently Used eviction policy.
    """

    __key__ = "tlru-c"


class TLruClusterMultiplePolicy(TLruScriptsMixin, PickleMd5HashMixin, BaseClusterMultiplePolicy):
    """
    .. inheritance-diagram:: TLruClusterMultiplePolicy

    Each decorated function of the policy has its own key pair, with cluster support, use time based pseudo Least Recently Used eviction policy.
    """

    __key__ = "tlru-cm"
