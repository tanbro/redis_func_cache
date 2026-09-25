"""FIFO eviction policies."""

from .hashing import PICKLE_MD5_HASHER
from .keying import ClusterMultipleKeying, ClusterSingleKeying, MultipleKeying, SingleKeying
from .policy import Policy
from .scripts import FifoScripts, FifoTScripts

__all__ = (
    "FifoClusterMultiplePolicy",
    "FifoClusterPolicy",
    "FifoMultiplePolicy",
    "FifoPolicy",
    "FifoTClusterMultiplePolicy",
    "FifoTClusterPolicy",
    "FifoTMultiplePolicy",
    "FifoTPolicy",
)

#: FIFO eviction policy, single key pair shared by all decorated functions.
FifoPolicy = Policy(SingleKeying("fifo"), PICKLE_MD5_HASHER, FifoScripts())
#: FIFO eviction policy, one key pair per decorated function.
FifoMultiplePolicy = Policy(MultipleKeying("fifo-m"), PICKLE_MD5_HASHER, FifoScripts())
#: FIFO eviction policy with Redis cluster support, single key pair.
FifoClusterPolicy = Policy(ClusterSingleKeying("fifo-c"), PICKLE_MD5_HASHER, FifoScripts())
#: FIFO eviction policy with Redis cluster support, one key pair per decorated function.
FifoClusterMultiplePolicy = Policy(ClusterMultipleKeying("fifo-cm"), PICKLE_MD5_HASHER, FifoScripts())

#: FIFO eviction policy (timestamp variant), single key pair.
FifoTPolicy = Policy(SingleKeying("fifo_t"), PICKLE_MD5_HASHER, FifoTScripts())
#: FIFO eviction policy (timestamp variant), one key pair per decorated function.
FifoTMultiplePolicy = Policy(MultipleKeying("fifo_t-m"), PICKLE_MD5_HASHER, FifoTScripts())
#: FIFO eviction policy (timestamp variant) with Redis cluster support, single key pair.
FifoTClusterPolicy = Policy(ClusterSingleKeying("fifo_t-c"), PICKLE_MD5_HASHER, FifoTScripts())
#: FIFO eviction policy (timestamp variant) with Redis cluster support, one key pair per function.
FifoTClusterMultiplePolicy = Policy(ClusterMultipleKeying("fifo_t-cm"), PICKLE_MD5_HASHER, FifoTScripts())
