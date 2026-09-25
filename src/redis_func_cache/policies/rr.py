"""Random replacement eviction cache policy."""

from .hashing import PICKLE_MD5_HASHER
from .keying import ClusterMultipleKeying, ClusterSingleKeying, MultipleKeying, SingleKeying
from .policy import Policy
from .scripts import RrScripts

__all__ = ("RrClusterMultiplePolicy", "RrClusterPolicy", "RrMultiplePolicy", "RrPolicy")

#: Random replacement (RR) eviction policy, single key pair shared by all decorated functions.
RrPolicy = Policy(SingleKeying("rr"), PICKLE_MD5_HASHER, RrScripts())
#: Random replacement (RR) eviction policy, one key pair per decorated function.
RrMultiplePolicy = Policy(MultipleKeying("rr-m"), PICKLE_MD5_HASHER, RrScripts())
#: Random replacement (RR) eviction policy with Redis cluster support, single key pair.
RrClusterPolicy = Policy(ClusterSingleKeying("rr-c"), PICKLE_MD5_HASHER, RrScripts())
#: Random replacement (RR) eviction policy with Redis cluster support, one key pair per function.
RrClusterMultiplePolicy = Policy(ClusterMultipleKeying("rr-cm"), PICKLE_MD5_HASHER, RrScripts())
