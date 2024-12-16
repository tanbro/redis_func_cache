from ..mixins.hash import PickleMd5HashMixin
from ..mixins.policies import MruScriptsMixin
from .base import BaseClusterMultiplePolicy, BaseClusterSinglePolicy, BaseMultiplePolicy, BaseSinglePolicy

__all__ = ("MruPolicy", "MruMultiplePolicy", "MruClusterPolicy", "MruClusterMultiplePolicy")


class _MruPolicyExtArgsMixin:
    def calc_ext_args(self, *args, **kwargs):
        return ("mru",)


class MruPolicy(_MruPolicyExtArgsMixin, MruScriptsMixin, PickleMd5HashMixin, BaseSinglePolicy):
    """All functions are cached in a single sorted-set/hash-map pair of redis, with Most Recently Used eviction policy."""

    __key__ = "mru"


class MruMultiplePolicy(_MruPolicyExtArgsMixin, MruScriptsMixin, PickleMd5HashMixin, BaseMultiplePolicy):
    """Each function is cached in its own sorted-set/hash-map pair of redis, with Most Recently Used eviction policy."""

    __key__ = "mru-m"


class MruClusterPolicy(_MruPolicyExtArgsMixin, MruScriptsMixin, PickleMd5HashMixin, BaseClusterSinglePolicy):
    """All functions are cached in a single sorted-set/hash-map pair of redis with cluster support, with Most Recently Used eviction policy."""

    __key__ = "mru-c"


class MruClusterMultiplePolicy(_MruPolicyExtArgsMixin, MruScriptsMixin, PickleMd5HashMixin, BaseClusterMultiplePolicy):
    """Each function is cached in its own sorted-set/hash-map pair of redis with cluster support, with Most Recently Used eviction policy."""

    __key__ = "mru-cm"
