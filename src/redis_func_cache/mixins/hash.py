from __future__ import annotations

import hashlib
import json
import pickle
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Mapping, Optional, Sequence

from ..utils import base64_hash_digest, get_fullname, get_source

if TYPE_CHECKING:  # pragma: no cover
    from hashlib import _Hash

    from redis.typing import KeyT

__all__ = (
    "AbstractHashMixin",
    "JsonMd5HashMixin",
    "JsonMd5HexHashMixin",
    "JsonMd5Base64HashMixin",
    "JsonSha1HashMixin",
    "JsonSha1HexHashMixin",
    "JsonSha1Base64HashMixin",
    "PickleMd5HashMixin",
    "PickleMd5HexHashMixin",
    "PickleMd5Base64HashMixin",
    "PickleSha1HashMixin",
    "PickleSha1HexHashMixin",
    "PickleSha1Base64HashMixin",
)


@dataclass(frozen=True)
class HashConfig:
    """Configurator for :class:`.AbstractHashMixin`"""

    serializer: Callable[[Any], bytes]
    """function to serialize function name, source code, and arguments"""
    algorithm: str
    """name for hashing algorithm"""
    decoder: Optional[Callable[[_Hash], KeyT]] = None
    """function to convert hash digest to member of a sorted/unsorted set and also field name of a hash map in redis.

    Default is :data:`None`, means no convert and use the digested bytes directly.
    """


class AbstractHashMixin:
    """An abstract mixin class for hash function name, source code, and arguments.

    **Do NOT use the mixin class directly.**
    Override the class attribute :attr:`.__hash_config__` to define the algorithm and serializer.

    Attributes:
        __hash_config__: Configure of how to calculate hash for a function.


    Example:
        ::

            class Md5JsonHashMixin(AbstractHashMixin):
                __hash_config__ = HashConfig(algorithm="md5", serializer=lambda x: json.dumps(x).encode())
    """

    __hash_config__: HashConfig

    def calc_hash(
        self, f: Optional[Callable] = None, args: Optional[Sequence] = None, kwds: Optional[Mapping[str, Any]] = None
    ) -> KeyT:
        """Mixin method to overwrite :meth:`redis_func_cache.policies.abstract.AbstractPolicy.calc_hash`

        All other mixin classes in the module inherit this mixin class, and their ``hash`` value are all return by the method.

        They use different hash algorithms and serializers defined in the class attribute :attr:`.__hash_config__` to generate different ``hash`` value.
        """
        if not callable(f):
            raise TypeError(f"Can not calculate hash for {f=}")
        conf = self.__hash_config__
        h = hashlib.new(conf.algorithm)
        h.update(get_fullname(f).encode())
        source = get_source(f)
        if source is not None:
            h.update(source.encode())
        if args is not None:
            h.update(conf.serializer(args))
        if kwds is not None:
            h.update(conf.serializer(kwds))
        if conf.decoder is None:
            return h.digest()
        return conf.decoder(h)


def hexdigest(x: _Hash):
    return x.hexdigest()


def json_dump_to_bytes(x):
    return json.dumps(x).encode()


class JsonMd5HashMixin(AbstractHashMixin):
    """
    Serializes the function name, source code, and arguments using the :mod:`json` module,
    then calculates the MD5 hash value,
    and finally returns the digest as bytes.

    .. inheritance-diagram:: JsonMd5HashMixin
    """

    __hash_config__ = HashConfig(algorithm="md5", serializer=json_dump_to_bytes)


class JsonMd5HexHashMixin(AbstractHashMixin):
    """
    Serializes the function name, source code, and arguments using the :mod:`json` module,
    then calculates the MD5 hash value,
    and finally returns the hexadecimal representation of the digest.

    .. inheritance-diagram:: JsonMd5HexHashMixin
    """

    __hash_config__ = HashConfig(algorithm="md5", serializer=json_dump_to_bytes, decoder=hexdigest)


class JsonMd5Base64HashMixin(AbstractHashMixin):
    """
    Serializes the function name, source code, and arguments using the :mod:`json` module,
    then calculates the MD5 hash value,
    and finally returns the base64 encoded digest.

    .. inheritance-diagram:: JsonMd5Base64HashMixin
    """

    __hash_config__ = HashConfig(algorithm="md5", serializer=json_dump_to_bytes, decoder=base64_hash_digest)


class JsonSha1HashMixin(AbstractHashMixin):
    """
    Serializes the function name, source code, and arguments using the :mod:`json` module,
    then calculates the SHA1 hash value,
    and finally returns the digest as bytes.

    .. inheritance-diagram:: JsonSha1HashMixin
    """

    __hash_config__ = HashConfig(algorithm="sha1", serializer=json_dump_to_bytes)


class JsonSha1HexHashMixin(AbstractHashMixin):
    """
    Serializes the function name, source code, and arguments using the :mod:`json` module,
    then calculates the SHA1 hash value,
    and finally returns the hexadecimal representation of the digest.

    .. inheritance-diagram:: JsonSha1HexHashMixin
    """

    __hash_config__ = HashConfig(algorithm="sha1", serializer=json_dump_to_bytes, decoder=hexdigest)


class JsonSha1Base64HashMixin(AbstractHashMixin):
    """
    Serializes the function name, source code, and arguments using the :mod:`json` module,
    then calculates the SHA1 hash value,
    and finally returns the base64 encoded digest.

    .. inheritance-diagram:: JsonSha1Base64HashMixin
    """

    __hash_config__ = HashConfig(algorithm="sha1", serializer=json_dump_to_bytes, decoder=base64_hash_digest)


class PickleMd5HashMixin(AbstractHashMixin):
    """
    Serializes the function name, source code, and arguments using the :mod:`pickle` module,
    then calculates the MD5 hash value,
    and finally returns the digest as bytes.

    It is the default hash mixin.

    .. inheritance-diagram:: PickleMd5HashMixin
    """

    __hash_config__ = HashConfig(algorithm="md5", serializer=pickle.dumps)


class PickleMd5HexHashMixin(AbstractHashMixin):
    """
    Serializes the function name, source code, and arguments using the :mod:`pickle` module,
    then calculates the MD5 hash value,
    and finally returns the hexadecimal representation of the digest.

    .. inheritance-diagram:: PickleMd5HexHashMixin
    """

    __hash_config__ = HashConfig(algorithm="md5", serializer=pickle.dumps, decoder=hexdigest)


class PickleMd5Base64HashMixin(AbstractHashMixin):
    """
    Serializes the function name, source code, and arguments using the :mod:`pickle` module,
    then calculates the MD5 hash value,
    and finally returns the base64 encoded digest.

    .. inheritance-diagram:: PickleMd5Base64HashMixin
    """

    __hash_config__ = HashConfig(algorithm="md5", serializer=pickle.dumps, decoder=base64_hash_digest)


class PickleSha1HashMixin(AbstractHashMixin):
    """
    Serializes the function name, source code, and arguments using the :mod:`pickle` module,
    then calculates the SHA1 hash value,
    and finally returns the digest as bytes.

    .. inheritance-diagram:: PickleSha1HashMixin
    """

    __hash_config__ = HashConfig(algorithm="sha1", serializer=pickle.dumps)


class PickleSha1HexHashMixin(AbstractHashMixin):
    """
    Serializes the function name, source code, and arguments using the :mod:`pickle` module,
    then calculates the SHA1 hash value,
    and finally returns the hexadecimal representation of the digest.

    .. inheritance-diagram:: PickleSha1HexHashMixin
    """

    __hash_config__ = HashConfig(algorithm="sha1", serializer=pickle.dumps, decoder=hexdigest)


class PickleSha1Base64HashMixin(AbstractHashMixin):
    """
    Serializes the function name, source code, and arguments using the :mod:`pickle` module,
    then calculates the SHA1 hash value,
    and finally returns the base64 encoded digest.

    .. inheritance-diagram:: PickleSha1Base64HashMixin
    """

    __hash_config__ = HashConfig(algorithm="sha1", serializer=pickle.dumps, decoder=base64_hash_digest)
