"""Most Recently Used eviction cache policies."""

from ..hashing import PICKLE_MD5_HASHER
from ..keying import ClusterMultipleKeying, ClusterSingleKeying, MultipleKeying, SingleKeying
from ..scripts import MruScripts
from . import Policy

__all__ = ("mru_cluster_multiple_policy", "mru_cluster_policy", "mru_multiple_policy", "mru_policy")

#: MRU eviction policy, single key pair shared by all decorated functions.
mru_policy = Policy(SingleKeying("mru"), PICKLE_MD5_HASHER, MruScripts())
#: MRU eviction policy, one key pair per decorated function.
mru_multiple_policy = Policy(MultipleKeying("mru-m"), PICKLE_MD5_HASHER, MruScripts())
#: MRU eviction policy with Redis cluster support, single key pair.
mru_cluster_policy = Policy(ClusterSingleKeying("mru-c"), PICKLE_MD5_HASHER, MruScripts())
#: MRU eviction policy with Redis cluster support, one key pair per decorated function.
mru_cluster_multiple_policy = Policy(ClusterMultipleKeying("mru-cm"), PICKLE_MD5_HASHER, MruScripts())
