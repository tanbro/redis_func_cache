from ..mixins.hash import PickleMd5Base64HashMixin
from ..mixins.policies import TLruScriptsMixin
from .base import BaseClusterMultiplePolicy, BaseClusterSinglePolicy, BaseMultiplePolicy, BaseSinglePolicy

__all__ = ("TLruPolicy", "TLruMultiplePolicy", "TLruClusterPolicy", "TLruClusterMultiplePolicy")


class TLruPolicy(TLruScriptsMixin, PickleMd5Base64HashMixin, BaseSinglePolicy):
    """All decorated functions share the same key pair, use time based pseudo Least Recently Used eviction policy."""

    __key__ = "tlru"


class TLruMultiplePolicy(TLruScriptsMixin, PickleMd5Base64HashMixin, BaseMultiplePolicy):
    """Each decorated function of the policy has its own key pair, use time based pseudo Least Recently Used eviction policy."""

    __key__ = "tlru-m"


class TLruClusterPolicy(TLruScriptsMixin, PickleMd5Base64HashMixin, BaseClusterSinglePolicy):
    """All decorated functions share the same key pair, with cluster support, use time based pseudo Least Recently Used eviction policy."""

    __key__ = "tlru-c"


class TLruClusterMultiplePolicy(TLruScriptsMixin, PickleMd5Base64HashMixin, BaseClusterMultiplePolicy):
    """Each decorated function of the policy has its own key pair, with cluster support, use time based pseudo Least Recently Used eviction policy."""

    __key__ = "tlru-cm"
