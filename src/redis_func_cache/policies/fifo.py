"""FIFO eviction policies."""

from ..hashing import PICKLE_MD5_HASHER
from ..keying import ClusterMultipleKeying, ClusterSingleKeying, MultipleKeying, SingleKeying
from ..scripts import FifoScripts, FifoTScripts
from . import Policy

__all__ = (
    "fifo_cluster_multiple_policy",
    "fifo_cluster_policy",
    "fifo_multiple_policy",
    "fifo_policy",
    "fifo_t_cluster_multiple_policy",
    "fifo_t_cluster_policy",
    "fifo_t_multiple_policy",
    "fifo_t_policy",
)

#: FIFO eviction policy, single key pair shared by all decorated functions.
fifo_policy = Policy(SingleKeying("fifo"), PICKLE_MD5_HASHER, FifoScripts())
#: FIFO eviction policy, one key pair per decorated function.
fifo_multiple_policy = Policy(MultipleKeying("fifo-m"), PICKLE_MD5_HASHER, FifoScripts())
#: FIFO eviction policy with Redis cluster support, single key pair.
fifo_cluster_policy = Policy(ClusterSingleKeying("fifo-c"), PICKLE_MD5_HASHER, FifoScripts())
#: FIFO eviction policy with Redis cluster support, one key pair per decorated function.
fifo_cluster_multiple_policy = Policy(ClusterMultipleKeying("fifo-cm"), PICKLE_MD5_HASHER, FifoScripts())

#: FIFO eviction policy (timestamp variant), single key pair.
fifo_t_policy = Policy(SingleKeying("fifo_t"), PICKLE_MD5_HASHER, FifoTScripts())
#: FIFO eviction policy (timestamp variant), one key pair per decorated function.
fifo_t_multiple_policy = Policy(MultipleKeying("fifo_t-m"), PICKLE_MD5_HASHER, FifoTScripts())
#: FIFO eviction policy (timestamp variant) with Redis cluster support, single key pair.
fifo_t_cluster_policy = Policy(ClusterSingleKeying("fifo_t-c"), PICKLE_MD5_HASHER, FifoTScripts())
#: FIFO eviction policy (timestamp variant) with Redis cluster support, one key pair per function.
fifo_t_cluster_multiple_policy = Policy(ClusterMultipleKeying("fifo_t-cm"), PICKLE_MD5_HASHER, FifoTScripts())
