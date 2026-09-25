"""Most Recently Used eviction cache policies."""

from .hashing import PICKLE_MD5_HASHER
from .keying import ClusterMultipleKeying, ClusterSingleKeying, MultipleKeying, SingleKeying
from .policy import Policy
from .scripts import MruScripts

__all__ = ("MruClusterMultiplePolicy", "MruClusterPolicy", "MruMultiplePolicy", "MruPolicy")

#: MRU eviction policy, single key pair shared by all decorated functions.
MruPolicy = Policy(SingleKeying("mru"), PICKLE_MD5_HASHER, MruScripts())
#: MRU eviction policy, one key pair per decorated function.
MruMultiplePolicy = Policy(MultipleKeying("mru-m"), PICKLE_MD5_HASHER, MruScripts())
#: MRU eviction policy with Redis cluster support, single key pair.
MruClusterPolicy = Policy(ClusterSingleKeying("mru-c"), PICKLE_MD5_HASHER, MruScripts())
#: MRU eviction policy with Redis cluster support, one key pair per decorated function.
MruClusterMultiplePolicy = Policy(ClusterMultipleKeying("mru-cm"), PICKLE_MD5_HASHER, MruScripts())
