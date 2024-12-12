from ..mixins.md5hash import Md5PickleMixin
from ..mixins.policies import FifoScriptsMixin
from .base import BaseClusterMultiplePolicy, BaseClusterSinglePolicy, BaseMultiplePolicy, BaseSinglePolicy

__all__ = ("FifoPolicy", "FifoClusterPolicy", "FifoClusterMultiplePolicy", "FifoMultiplePolicy")


class FifoPolicy(FifoScriptsMixin, Md5PickleMixin, BaseSinglePolicy):
    """All decorated functions share the same key pair, use First In First Out eviction policy."""

    __key__ = "fifo"


class FifoMultiplePolicy(FifoScriptsMixin, Md5PickleMixin, BaseMultiplePolicy):
    """Each decorated function has its own key pair, use First In First Out eviction policy."""

    __key__ = "fifo-m"


class FifoClusterPolicy(FifoScriptsMixin, Md5PickleMixin, BaseClusterSinglePolicy):
    """All decorated functions share the same key pair, with cluster support, use First In First Out eviction policy."""

    __key__ = "fifo-c"


class FifoClusterMultiplePolicy(FifoScriptsMixin, Md5PickleMixin, BaseClusterMultiplePolicy):
    """Each decorated function has its own key pair, with cluster support, use First In First Out eviction policy."""

    __key__ = "fifo-cm"
