"""LFU eviction policy."""

from ..hashing import PICKLE_MD5_HASHER
from ..keying import ClusterMultipleKeying, ClusterSingleKeying, MultipleKeying, SingleKeying
from ..scripts import LfuScripts
from . import Policy

__all__ = ("lfu_cluster_multiple_policy", "lfu_cluster_policy", "lfu_multiple_policy", "lfu_policy")

#: LFU eviction policy, single key pair shared by all decorated functions.
lfu_policy = Policy(SingleKeying("lfu"), PICKLE_MD5_HASHER, LfuScripts())
#: LFU eviction policy, one key pair per decorated function.
lfu_multiple_policy = Policy(MultipleKeying("lfu-m"), PICKLE_MD5_HASHER, LfuScripts())
#: LFU eviction policy with Redis cluster support, single key pair.
lfu_cluster_policy = Policy(ClusterSingleKeying("lfu-c"), PICKLE_MD5_HASHER, LfuScripts())
#: LFU eviction policy with Redis cluster support, one key pair per decorated function.
lfu_cluster_multiple_policy = Policy(ClusterMultipleKeying("lfu-cm"), PICKLE_MD5_HASHER, LfuScripts())
