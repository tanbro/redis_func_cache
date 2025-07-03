from ..mixins.hash import PickleMd5HashMixin
from ..mixins.scripts import MruScriptsMixin
from .base import BaseClusterMultiplePolicy, BaseClusterSinglePolicy, BaseMultiplePolicy, BaseSinglePolicy

__all__ = ("MruPolicy", "MruMultiplePolicy", "MruClusterPolicy", "MruClusterMultiplePolicy")


class _MruPolicyExtArgsMixin:
    def calc_ext_args(self, *args, **kwargs):
        return ("mru",)


class MruPolicy(_MruPolicyExtArgsMixin, MruScriptsMixin, PickleMd5HashMixin, BaseSinglePolicy):
    """
    MRU eviction policy, single key pair.

    All decorated functions share the same Redis key pair.
    """

    __key__ = "mru"


class MruMultiplePolicy(_MruPolicyExtArgsMixin, MruScriptsMixin, PickleMd5HashMixin, BaseMultiplePolicy):
    """
    MRU eviction policy, multiple key pairs.

    Each decorated function has its own Redis key pair.
    """

    __key__ = "mru-m"


class MruClusterPolicy(_MruPolicyExtArgsMixin, MruScriptsMixin, PickleMd5HashMixin, BaseClusterSinglePolicy):
    """
    MRU eviction policy with Redis cluster support, single key pair.

    All decorated functions share the same Redis key pair.
    """

    __key__ = "mru-c"


class MruClusterMultiplePolicy(_MruPolicyExtArgsMixin, MruScriptsMixin, PickleMd5HashMixin, BaseClusterMultiplePolicy):
    """
    MRU eviction policy with Redis cluster support, multiple key pairs.

    Each decorated function has its own Redis key pair.
    """

    __key__ = "mru-cm"
