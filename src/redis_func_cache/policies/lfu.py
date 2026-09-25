"""LFU eviction policy."""

from ..hashing import PICKLE_MD5_HASHER
from ..keying import ClusterMultipleKeying, ClusterSingleKeying, MultipleKeying, SingleKeying
from ..scripts import LfuScripts
from . import Policy

__all__ = ("LfuClusterMultiplePolicy", "LfuClusterPolicy", "LfuMultiplePolicy", "LfuPolicy")

#: LFU eviction policy, single key pair shared by all decorated functions.
LfuPolicy = Policy(SingleKeying("lfu"), PICKLE_MD5_HASHER, LfuScripts())
#: LFU eviction policy, one key pair per decorated function.
LfuMultiplePolicy = Policy(MultipleKeying("lfu-m"), PICKLE_MD5_HASHER, LfuScripts())
#: LFU eviction policy with Redis cluster support, single key pair.
LfuClusterPolicy = Policy(ClusterSingleKeying("lfu-c"), PICKLE_MD5_HASHER, LfuScripts())
#: LFU eviction policy with Redis cluster support, one key pair per decorated function.
LfuClusterMultiplePolicy = Policy(ClusterMultipleKeying("lfu-cm"), PICKLE_MD5_HASHER, LfuScripts())
