from __future__ import annotations

import hashlib
import json
import pickle
from abc import ABC
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from ..utils import b64digest, calculate_callable_fullname, get_callable_bytecode

if TYPE_CHECKING:  # pragma: no cover
    from redis.typing import KeyT

    from ..typing import Hash

__all__ = (
    "AbstractHashMixin",
    "HashConfig",
    "JsonMd5Base64HashMixin",
    "JsonMd5HashMixin",
    "JsonMd5HexHashMixin",
    "JsonSha1Base64HashMixin",
    "JsonSha1HashMixin",
    "JsonSha1HexHashMixin",
    "JsonSha256Base64HashMixin",
    "JsonSha256HashMixin",
    "JsonSha256HexHashMixin",
    "JsonSha512Base64HashMixin",
    "JsonSha512HashMixin",
    "JsonSha512HexHashMixin",
    "PickleMd5Base64HashMixin",
    "PickleMd5HashMixin",
    "PickleMd5HexHashMixin",
    "PickleSha1Base64HashMixin",
    "PickleSha1HashMixin",
    "PickleSha1HexHashMixin",
    "PickleSha256Base64HashMixin",
    "PickleSha256HashMixin",
    "PickleSha256HexHashMixin",
    "PickleSha512Base64HashMixin",
    "PickleSha512HashMixin",
    "PickleSha512HexHashMixin",
)


@dataclass(frozen=True)
class HashConfig:
    """A :func:`dataclasses.dataclass` Configurator for :class:`.AbstractHashMixin`"""

    algorithm: str
    """name for hashing algorithm

    The name must be supported by :mod:`hashlib`.
    """
    serializer: Callable[[Any], bytes]
    """function to serialize function positional and keyword arguments."""
    decoder: Callable[[Hash], KeyT] | None = None
    """function to decode hash digest to member of a sorted/unsorted set and also field name of a hash map in redis.

    Default is :data:`None`, means no decoding and to use the raw digest bytes directly.
    """
    use_bytecode: bool = True
    """whether to use bytecode of the function to calculate hash.

    .. versionadded:: 0.5
    """


# Cache of hash objects seeded with a callable's fingerprint (its fullname plus optional bytecode — the inputs that never change for a given function object), per (algorithm, bytecode flag, function).
# Hash digests are defined over the byte stream, so seeding incrementally is identical to hashing the concatenation;
# a seeded object can thus be shared as long as callers .copy() it before feeding per-invocation data.
#
# The cache key deliberately holds only the fields the fingerprint consumes — configs
# differing in serializer/decoder produce identical fingerprints and share entries.
# ``lru_cache`` keys on the callable object itself (functions hash by identity), so a live function can never collide with a stale entry.
# The trade-off of identity keying is a strong reference: collected functions linger until LRU-evicted, which the bounded maxsize caps — only pathological dynamic-callable usage can reach it.
MAX_FINGERPRINT_HASH_ENTRIES = 1024


@lru_cache(maxsize=MAX_FINGERPRINT_HASH_ENTRIES)
def _fingerprint_hash(algorithm: str, use_bytecode: bool, fn: Callable) -> Hash:
    """Return the hash object seeded with the fingerprint of ``fn``.

    The fingerprint (callable fullname plus optional bytecode) is immutable for a
    given function object, so it is hashed once and reused via ``copy()``. The
    cached object itself must never be updated — always operate on a copy.
    """
    h = hashlib.new(algorithm)
    h.update(calculate_callable_fullname(fn).encode())
    if use_bytecode:
        h.update(get_callable_bytecode(fn))
    return h


class AbstractHashMixin(ABC):
    """An abstract mixin class for hash function name, source code, and arguments.

    .. inheritance-diagram:: AbstractHashMixin
        :parts: 1

    The hash result is used inside the redis (ordered) set and hash map in redis, aka the sub-key.

    **Do NOT use the mixin class directly.**
    Inherit it and override the :attr:`.__hash_config__` to define the algorithm and serializer.

    Example:

        ::

            class JsonMd5B64HashMixin(AbstractHashMixin):
                __hash_config__ = HashConfig(
                    algorithm="md5",
                    serializer=lambda x: json.dumps(x).encode(),
                    decoder=lambda x: b64encode(x.digest()),
                )

    Attributes:
        __hash_config__ (HashConfig): Configure of how to calculate hash for a function.
    """

    __hash_config__: HashConfig

    def calc_hash(
        self,
        fn: Callable | None = None,
        args: tuple[Any, ...] | None = None,
        kwds: dict[str, Any] | None = None,
    ) -> KeyT:
        """Mixin method to overwrite :meth:`redis_func_cache.policies.abstract.AbstractPolicy.calc_hash`

        All other mixin classes in the module inherit this mixin class, and their ``hash`` value are all return by the method.

        They use different hash algorithms and serializers defined in the class attribute :attr:`.__hash_config__` to generate different ``hash`` value.

        Args:
            fn: The function to calculate hash for.
            args: The :term`sequence` arguments of the function.
            kwds: The keyword arguments of the function.

        Returns:
            The hash value of the function.

        Raises:
            TypeError: If the function is not callable.
        """
        if fn is None:
            raise TypeError("Can not calculate hash for None")
        conf = self.__hash_config__
        h = _fingerprint_hash(conf.algorithm, conf.use_bytecode, fn).copy()
        if args is not None:
            h.update(conf.serializer(args))
        if kwds is not None:
            h.update(conf.serializer(kwds))
        if conf.decoder is None:
            return h.digest()
        return conf.decoder(h)


JSON_SERIALIZER = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":")).encode()
HEX_DIGEST_DECODER = lambda x: x.hexdigest()


class JsonMd5HashMixin(AbstractHashMixin):
    """
    Serializes the function name, source code, and arguments using the :mod:`json` module,
    then calculates the MD5 hash value,
    and finally returns the digest as bytes.

    .. inheritance-diagram:: JsonMd5HashMixin
        :parts: 1
    """

    __hash_config__ = HashConfig(algorithm="md5", serializer=JSON_SERIALIZER)


class JsonMd5HexHashMixin(AbstractHashMixin):
    """
    Serializes the function name, source code, and arguments using the :mod:`json` module,
    then calculates the MD5 hash value,
    and finally returns the hexadecimal representation of the digest.

    .. inheritance-diagram:: JsonMd5HexHashMixin
        :parts: 1
    """

    __hash_config__ = HashConfig(algorithm="md5", serializer=JSON_SERIALIZER, decoder=HEX_DIGEST_DECODER)


class JsonMd5Base64HashMixin(AbstractHashMixin):
    """
    Serializes the function name, source code, and arguments using the :mod:`json` module,
    then calculates the MD5 hash value,
    and finally returns the base64 encoded digest.

    .. inheritance-diagram:: JsonMd5Base64HashMixin
        :parts: 1
    """

    __hash_config__ = HashConfig(algorithm="md5", serializer=JSON_SERIALIZER, decoder=b64digest)


class JsonSha1HashMixin(AbstractHashMixin):
    """
    Serializes the function name, source code, and arguments using the :mod:`json` module,
    then calculates the SHA1 hash value,
    and finally returns the digest as bytes.

    .. inheritance-diagram:: JsonSha1HashMixin
        :parts: 1
    """

    __hash_config__ = HashConfig(algorithm="sha1", serializer=JSON_SERIALIZER)


class JsonSha1HexHashMixin(AbstractHashMixin):
    """
    Serializes the function name, source code, and arguments using the :mod:`json` module,
    then calculates the SHA1 hash value,
    and finally returns the hexadecimal representation of the digest.

    .. inheritance-diagram:: JsonSha1HexHashMixin
        :parts: 1
    """

    __hash_config__ = HashConfig(algorithm="sha1", serializer=JSON_SERIALIZER, decoder=HEX_DIGEST_DECODER)


class JsonSha1Base64HashMixin(AbstractHashMixin):
    """
    Serializes the function name, source code, and arguments using the :mod:`json` module,
    then calculates the SHA1 hash value,
    and finally returns the base64 encoded digest.

    .. inheritance-diagram:: JsonSha1Base64HashMixin
        :parts: 1
    """

    __hash_config__ = HashConfig(algorithm="sha1", serializer=JSON_SERIALIZER, decoder=b64digest)


class JsonSha256HashMixin(AbstractHashMixin):
    """
    Serializes the function name, source code, and arguments using the :mod:`json` module,
    then calculates the SHA256 hash value,
    and finally returns the digest as bytes.

    .. inheritance-diagram:: JsonSha256HashMixin
        :parts: 1
    """

    __hash_config__ = HashConfig(algorithm="sha256", serializer=JSON_SERIALIZER)


class JsonSha256HexHashMixin(AbstractHashMixin):
    """
    Serializes the function name, source code, and arguments using the :mod:`json` module,
    then calculates the SHA256 hash value,
    and finally returns the hexadecimal representation of the digest.

    .. inheritance-diagram:: JsonSha256HexHashMixin
        :parts: 1
    """

    __hash_config__ = HashConfig(algorithm="sha256", serializer=JSON_SERIALIZER, decoder=HEX_DIGEST_DECODER)


class JsonSha256Base64HashMixin(AbstractHashMixin):
    """
    Serializes the function name, source code, and arguments using the :mod:`json` module,
    then calculates the SHA256 hash value,
    and finally returns the base64 encoded digest.

    .. inheritance-diagram:: JsonSha256Base64HashMixin
        :parts: 1
    """

    __hash_config__ = HashConfig(algorithm="sha256", serializer=JSON_SERIALIZER, decoder=b64digest)


class JsonSha512HashMixin(AbstractHashMixin):
    """
    Serializes the function name, source code, and arguments using the :mod:`json` module,
    then calculates the SHA512 hash value,
    and finally returns the digest as bytes.

    .. inheritance-diagram:: JsonSha512HashMixin
        :parts: 1
    """

    __hash_config__ = HashConfig(algorithm="sha512", serializer=JSON_SERIALIZER)


class JsonSha512HexHashMixin(AbstractHashMixin):
    """
    Serializes the function name, source code, and arguments using the :mod:`json` module,
    then calculates the SHA512 hash value,
    and finally returns the hexadecimal representation of the digest.

    .. inheritance-diagram:: JsonSha512HexHashMixin
        :parts: 1
    """

    __hash_config__ = HashConfig(algorithm="sha512", serializer=JSON_SERIALIZER, decoder=HEX_DIGEST_DECODER)


class JsonSha512Base64HashMixin(AbstractHashMixin):
    """
    Serializes the function name, source code, and arguments using the :mod:`json` module,
    then calculates the SHA512 hash value,
    and finally returns the base64 encoded digest.

    .. inheritance-diagram:: JsonSha512Base64HashMixin
        :parts: 1
    """

    __hash_config__ = HashConfig(algorithm="sha512", serializer=JSON_SERIALIZER, decoder=b64digest)


class PickleMd5HashMixin(AbstractHashMixin):
    """
    Serializes the function name, source code, and arguments using the :mod:`pickle` module,
    then calculates the MD5 hash value,
    and finally returns the digest as bytes.

    It is the default hash mixin.

    .. inheritance-diagram:: PickleMd5HashMixin
        :parts: 1
    """

    __hash_config__ = HashConfig(algorithm="md5", serializer=pickle.dumps)


class PickleMd5HexHashMixin(AbstractHashMixin):
    """
    Serializes the function name, source code, and arguments using the :mod:`pickle` module,
    then calculates the MD5 hash value, and finally returns the hexadecimal representation of the digest.

    .. inheritance-diagram:: PickleMd5HexHashMixin
        :parts: 1
    """

    __hash_config__ = HashConfig(algorithm="md5", serializer=pickle.dumps, decoder=HEX_DIGEST_DECODER)


class PickleMd5Base64HashMixin(AbstractHashMixin):
    """
    Serializes the function name, source code, and arguments using the :mod:`pickle` module,
    then calculates the MD5 hash value, and finally returns the base64 encoded digest.

    .. inheritance-diagram:: PickleMd5Base64HashMixin
        :parts: 1
    """

    __hash_config__ = HashConfig(algorithm="md5", serializer=pickle.dumps, decoder=b64digest)


class PickleSha1HashMixin(AbstractHashMixin):
    """
    Serializes the function name, source code, and arguments using the :mod:`pickle` module,
    then calculates the SHA1 hash value,
    and finally returns the digest as bytes.

    .. inheritance-diagram:: PickleSha1HashMixin
        :parts: 1
    """

    __hash_config__ = HashConfig(algorithm="sha1", serializer=pickle.dumps)


class PickleSha1HexHashMixin(AbstractHashMixin):
    """
    Serializes the function name, source code, and arguments using the :mod:`pickle` module,
    then calculates the SHA1 hash value,
    and finally returns the hexadecimal representation of the digest.

    .. inheritance-diagram:: PickleSha1HexHashMixin
        :parts: 1
    """

    __hash_config__ = HashConfig(algorithm="sha1", serializer=pickle.dumps, decoder=HEX_DIGEST_DECODER)


class PickleSha1Base64HashMixin(AbstractHashMixin):
    """
    Serializes the function name, source code, and arguments using the :mod:`pickle` module,
    then calculates the SHA1 hash value,
    and finally returns the base64 encoded digest.

    .. inheritance-diagram:: PickleSha1Base64HashMixin
        :parts: 1
    """

    __hash_config__ = HashConfig(algorithm="sha1", serializer=pickle.dumps, decoder=b64digest)


class PickleSha256HashMixin(AbstractHashMixin):
    """
    Serializes the function name, source code, and arguments using the :mod:`pickle` module,
    then calculates the SHA256 hash value,
    and finally returns the digest as bytes.

    .. inheritance-diagram:: PickleSha256HashMixin
        :parts: 1
    """

    __hash_config__ = HashConfig(algorithm="sha256", serializer=pickle.dumps)


class PickleSha256HexHashMixin(AbstractHashMixin):
    """
    Serializes the function name, source code, and arguments using the :mod:`pickle` module,
    then calculates the SHA256 hash value,
    and finally returns the hexadecimal representation of the digest.

    .. inheritance-diagram:: PickleSha256HexHashMixin
        :parts: 1
    """

    __hash_config__ = HashConfig(algorithm="sha256", serializer=pickle.dumps, decoder=HEX_DIGEST_DECODER)


class PickleSha256Base64HashMixin(AbstractHashMixin):
    """
    Serializes the function name, source code, and arguments using the :mod:`pickle` module,
    then calculates the SHA256 hash value,
    and finally returns the base64 encoded digest.

    .. inheritance-diagram:: PickleSha256Base64HashMixin
        :parts: 1
    """

    __hash_config__ = HashConfig(algorithm="sha256", serializer=pickle.dumps, decoder=b64digest)


class PickleSha512HashMixin(AbstractHashMixin):
    """
    Serializes the function name, source code, and arguments using the :mod:`pickle` module,
    then calculates the SHA512 hash value,
    and finally returns the digest as bytes.

    .. inheritance-diagram:: PickleSha512HashMixin
        :parts: 1
    """

    __hash_config__ = HashConfig(algorithm="sha512", serializer=pickle.dumps)


class PickleSha512HexHashMixin(AbstractHashMixin):
    """
    Serializes the function name, source code, and arguments using the :mod:`pickle` module,
    then calculates the SHA512 hash value,
    and finally returns the hexadecimal representation of the digest.

    .. inheritance-diagram:: PickleSha512HexHashMixin
        :parts: 1
    """

    __hash_config__ = HashConfig(algorithm="sha512", serializer=pickle.dumps, decoder=HEX_DIGEST_DECODER)


class PickleSha512Base64HashMixin(AbstractHashMixin):
    """
    Serializes the function name, source code, and arguments using the :mod:`pickle` module,
    then calculates the SHA512 hash value,
    and finally returns the base64 encoded digest.

    .. inheritance-diagram:: PickleSha512Base64HashMixin
        :parts: 1
    """

    __hash_config__ = HashConfig(algorithm="sha512", serializer=pickle.dumps, decoder=b64digest)
