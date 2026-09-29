"""GDSF (Greedy-Dual-Size) eviction policy.

Score = ``freq * cost / size`` (Cherkasova 1998): the retained benefit per
byte, where ``size`` is the serialized byte length of the stored value and
``cost`` is the per-function miss cost declared with the ``cost`` decorator
kwarg (default 1.0). Note ``cost`` only influences eviction under the
single-key-pair keying variants (``gdsf_policy`` / ``gdsf_cluster_policy``);
under the per-function variants every key pair holds one function's entries,
so its cost is an in-pair constant and scoring reduces to frequency/size.
"""

from ..hashing import PICKLE_MD5_HASHER
from ..keying import ClusterMultipleKeying, ClusterSingleKeying, MultipleKeying, SingleKeying
from ..scripts import GdsfScripts
from . import Policy

__all__ = (
    "gdsf_cluster_multiple_policy",
    "gdsf_cluster_policy",
    "gdsf_multiple_policy",
    "gdsf_policy",
)

#: GDSF eviction policy, single key pair shared by all decorated functions.
gdsf_policy = Policy(SingleKeying("gdsf"), PICKLE_MD5_HASHER, GdsfScripts())
#: GDSF eviction policy, one key pair per decorated function.
gdsf_multiple_policy = Policy(MultipleKeying("gdsf-m"), PICKLE_MD5_HASHER, GdsfScripts())
#: GDSF eviction policy with Redis cluster support, single key pair.
gdsf_cluster_policy = Policy(ClusterSingleKeying("gdsf-c"), PICKLE_MD5_HASHER, GdsfScripts())
#: GDSF eviction policy with Redis cluster support, one key pair per decorated function.
gdsf_cluster_multiple_policy = Policy(ClusterMultipleKeying("gdsf-cm"), PICKLE_MD5_HASHER, GdsfScripts())
