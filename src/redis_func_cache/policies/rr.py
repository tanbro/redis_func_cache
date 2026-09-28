"""Random replacement eviction cache policy."""

from ..hashing import PICKLE_MD5_HASHER
from ..keying import ClusterMultipleKeying, ClusterSingleKeying, MultipleKeying, SingleKeying
from ..scripts import RrScripts
from . import Policy

__all__ = ("rr_cluster_multiple_policy", "rr_cluster_policy", "rr_multiple_policy", "rr_policy")

#: Random replacement (RR) eviction policy, single key pair shared by all decorated functions.
rr_policy = Policy(SingleKeying("rr"), PICKLE_MD5_HASHER, RrScripts())
#: Random replacement (RR) eviction policy, one key pair per decorated function.
rr_multiple_policy = Policy(MultipleKeying("rr-m"), PICKLE_MD5_HASHER, RrScripts())
#: Random replacement (RR) eviction policy with Redis cluster support, single key pair.
rr_cluster_policy = Policy(ClusterSingleKeying("rr-c"), PICKLE_MD5_HASHER, RrScripts())
#: Random replacement (RR) eviction policy with Redis cluster support, one key pair per function.
rr_cluster_multiple_policy = Policy(ClusterMultipleKeying("rr-cm"), PICKLE_MD5_HASHER, RrScripts())
