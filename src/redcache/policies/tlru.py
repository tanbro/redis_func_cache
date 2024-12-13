from ..mixins.md5hash import Md5PickleMixin
from ..mixins.policies import TLruScriptsMixin
from .base import BaseClusterMultiplePolicy, BaseClusterSinglePolicy, BaseMultiplePolicy, BaseSinglePolicy

__all__ = ("TLruPolicy", "TLruMultiplePolicy", "TLruClusterPolicy", "TLruClusterMultiplePolicy")


class TLruPolicy(TLruScriptsMixin, Md5PickleMixin, BaseSinglePolicy):
    """All decorated functions share the same key pair, use time based pseudo Least Recently Used eviction policy."""

    __key__ = "tlru"


class TLruMultiplePolicy(TLruScriptsMixin, Md5PickleMixin, BaseMultiplePolicy):
    """Each decorated function of the policy has its own key pair, use time based pseudo Least Recently Used eviction policy."""

    __key__ = "tlru-m"


class TLruClusterPolicy(TLruScriptsMixin, Md5PickleMixin, BaseClusterSinglePolicy):
    """All decorated functions share the same key pair, with cluster support, use time based pseudo Least Recently Used eviction policy."""

    __key__ = "tlru-c"


class TLruClusterMultiplePolicy(TLruScriptsMixin, Md5PickleMixin, BaseClusterMultiplePolicy):
    """Each decorated function of the policy has its own key pair, with cluster support, use time based pseudo Least Recently Used eviction policy."""

    __key__ = "tlru-cm"
