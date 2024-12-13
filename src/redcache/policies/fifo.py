from ..mixins.hash import PickleMd5Base64HashMixin
from ..mixins.policies import FifoScriptsMixin
from .base import BaseClusterMultiplePolicy, BaseClusterSinglePolicy, BaseMultiplePolicy, BaseSinglePolicy

__all__ = ("FifoPolicy", "FifoClusterPolicy", "FifoClusterMultiplePolicy", "FifoMultiplePolicy")


class FifoPolicy(FifoScriptsMixin, PickleMd5Base64HashMixin, BaseSinglePolicy):
    """All decorated functions share the same key pair, use First In First Out eviction policy."""

    __key__ = "fifo"


class FifoMultiplePolicy(FifoScriptsMixin, PickleMd5Base64HashMixin, BaseMultiplePolicy):
    """Each decorated function has its own key pair, use First In First Out eviction policy."""

    __key__ = "fifo-m"


class FifoClusterPolicy(FifoScriptsMixin, PickleMd5Base64HashMixin, BaseClusterSinglePolicy):
    """All decorated functions share the same key pair, with cluster support, use First In First Out eviction policy."""

    __key__ = "fifo-c"


class FifoClusterMultiplePolicy(FifoScriptsMixin, PickleMd5Base64HashMixin, BaseClusterMultiplePolicy):
    """Each decorated function has its own key pair, with cluster support, use First In First Out eviction policy."""

    __key__ = "fifo-cm"
