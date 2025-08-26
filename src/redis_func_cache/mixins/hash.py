from __future__ import annotations

import hashlib
import json
import pickle
from abc import ABC
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Tuple

from ..utils import b64digest, get_callable_bytecode

if TYPE_CHECKING:  # pragma: no cover
    from redis.typing import KeyT

    from ..typing import Hash

__all__ = (
    "HashConfig",
    "AbstractHashMixin",
    "JsonMd5HashMixin",
    "JsonMd5HexHashMixin",
    "JsonMd5Base64HashMixin",
    "JsonSha1HashMixin",
    "JsonSha1HexHashMixin",
    "JsonSha1Base64HashMixin",
    "JsonSha256HashMixin",
    "JsonSha256HexHashMixin",
    "JsonSha256Base64HashMixin",
    "JsonSha512HashMixin",
    "JsonSha512HexHashMixin",
    "JsonSha512Base64HashMixin",
    "PickleMd5HashMixin",
    "PickleMd5HexHashMixin",
    "PickleMd5Base64HashMixin",
    "PickleSha1HashMixin",
    "PickleSha1HexHashMixin",
    "PickleSha1Base64HashMixin",
    "PickleSha256HashMixin",
    "PickleSha256HexHashMixin",
    "PickleSha256Base64HashMixin",
    "PickleSha512HashMixin",
    "PickleSha512HexHashMixin",
    "PickleSha512Base64HashMixin",
)


@dataclass(frozen=True)
class HashConfig:
    """A :func:`dataclasses.dataclass` Configurator for :class:`.AbstractHashMixin`"""

    serializer: Callable[[Any], bytes]
    """function to serialize function positional and keyword arguments."""
    algorithm: str
    """name for hashing algorithm

    The name must be supported by :mod:`hashlib`.
    """
    decoder: Optional[Callable[[Hash], KeyT]] = None
    """function to decode hash digest to member of a sorted/unsorted set and also field name of a hash map in redis.

    Default is :data:`None`, means no decoding and to use the raw digest bytes directly.
    """
    use_bytecode: bool = True
    """whether to use bytecode of the function to calculate hash.

    .. versionadded:: 0.5
    """


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
        f: Optional[Callable] = None,
        args: Optional[Tuple[Any, ...]] = None,
        kwds: Optional[Dict[str, Any]] = None,
    ) -> KeyT:
        """Mixin method to overwrite :meth:`redis_func_cache.policies.abstract.AbstractPolicy.calc_hash`

        All other mixin classes in the module inherit this mixin class, and their ``hash`` value are all return by the method.

        They use different hash algorithms and serializers defined in the class attribute :attr:`.__hash_config__` to generate different ``hash`` value.

        Args:
            f: The function to calculate hash for.
            args: The :term`sequence` arguments of the function.
            kwds: The keyword arguments of the function.

        Returns:
            The hash value of the function.

        Raises:
            TypeError: If the function is not callable.
        """
        if not callable(f):
            raise TypeError("Can not calculate hash for a non-callable object")
        conf = self.__hash_config__
        hash = hashlib.new(conf.algorithm)
        hash.update(f"{f.__module__}:{f.__qualname__}".encode())
        if conf.use_bytecode:
            hash.update(get_callable_bytecode(f))
        if args is not None:
            hash.update(conf.serializer(args))
        if kwds is not None:
            hash.update(conf.serializer(kwds))
        if conf.decoder is None:
            return hash.digest()
        return conf.decoder(hash)


class JsonMd5HashMixin(AbstractHashMixin):
    """
    Serializes the function name, source code, and arguments using the :mod:`json` module,
    then calculates the MD5 hash value,
    and finally returns the digest as bytes.

    .. inheritance-diagram:: JsonMd5HashMixin
        :parts: 1
    """

    __hash_config__ = HashConfig(algorithm="md5", serializer=lambda x: json.dumps(x).encode())


class JsonMd5HexHashMixin(AbstractHashMixin):
    """
    Serializes the function name, source code, and arguments using the :mod:`json` module,
    then calculates the MD5 hash value,
    and finally returns the hexadecimal representation of the digest.

    .. inheritance-diagram:: JsonMd5HexHashMixin
        :parts: 1
    """

    __hash_config__ = HashConfig(
        algorithm="md5", serializer=lambda x: json.dumps(x).encode(), decoder=lambda x: x.hexdigest()
    )


class JsonMd5Base64HashMixin(AbstractHashMixin):
    """
    Serializes the function name, source code, and arguments using the :mod:`json` module,
    then calculates the MD5 hash value,
    and finally returns the base64 encoded digest.

    .. inheritance-diagram:: JsonMd5Base64HashMixin
        :parts: 1
    """

    __hash_config__ = HashConfig(
        algorithm="md5",
        serializer=lambda x: json.dumps(x).encode(),
        decoder=b64digest,
    )


class JsonSha1HashMixin(AbstractHashMixin):
    """
    Serializes the function name, source code, and arguments using the :mod:`json` module,
    then calculates the SHA1 hash value,
    and finally returns the digest as bytes.

    .. inheritance-diagram:: JsonSha1HashMixin
        :parts: 1
    """

    __hash_config__ = HashConfig(algorithm="sha1", serializer=lambda x: json.dumps(x).encode())


class JsonSha1HexHashMixin(AbstractHashMixin):
    """
    Serializes the function name, source code, and arguments using the :mod:`json` module,
    then calculates the SHA1 hash value,
    and finally returns the hexadecimal representation of the digest.

    .. inheritance-diagram:: JsonSha1HexHashMixin
        :parts: 1
    """

    __hash_config__ = HashConfig(
        algorithm="sha1", serializer=lambda x: json.dumps(x).encode(), decoder=lambda x: x.hexdigest()
    )


class JsonSha1Base64HashMixin(AbstractHashMixin):
    """
    Serializes the function name, source code, and arguments using the :mod:`json` module,
    then calculates the SHA1 hash value,
    and finally returns the base64 encoded digest.

    .. inheritance-diagram:: JsonSha1Base64HashMixin
        :parts: 1
    """

    __hash_config__ = HashConfig(
        algorithm="sha1",
        serializer=lambda x: json.dumps(x).encode(),
        decoder=b64digest,
    )


class JsonSha256HashMixin(AbstractHashMixin):
    """
    Serializes the function name, source code, and arguments using the :mod:`json` module,
    then calculates the SHA256 hash value,
    and finally returns the digest as bytes.

    .. inheritance-diagram:: JsonSha256HashMixin
        :parts: 1
    """

    __hash_config__ = HashConfig(algorithm="sha256", serializer=lambda x: json.dumps(x).encode())


class JsonSha256HexHashMixin(AbstractHashMixin):
    """
    Serializes the function name, source code, and arguments using the :mod:`json` module,
    then calculates the SHA256 hash value,
    and finally returns the hexadecimal representation of the digest.

    .. inheritance-diagram:: JsonSha256HexHashMixin
        :parts: 1
    """

    __hash_config__ = HashConfig(
        algorithm="sha256", serializer=lambda x: json.dumps(x).encode(), decoder=lambda x: x.hexdigest()
    )


class JsonSha256Base64HashMixin(AbstractHashMixin):
    """
    Serializes the function name, source code, and arguments using the :mod:`json` module,
    then calculates the SHA256 hash value,
    and finally returns the base64 encoded digest.

    .. inheritance-diagram:: JsonSha256Base64HashMixin
        :parts: 1
    """

    __hash_config__ = HashConfig(
        algorithm="sha256",
        serializer=lambda x: json.dumps(x).encode(),
        decoder=b64digest,
    )


class JsonSha512HashMixin(AbstractHashMixin):
    """
    Serializes the function name, source code, and arguments using the :mod:`json` module,
    then calculates the SHA512 hash value,
    and finally returns the digest as bytes.

    .. inheritance-diagram:: JsonSha512HashMixin
        :parts: 1
    """

    __hash_config__ = HashConfig(algorithm="sha512", serializer=lambda x: json.dumps(x).encode())


class JsonSha512HexHashMixin(AbstractHashMixin):
    """
    Serializes the function name, source code, and arguments using the :mod:`json` module,
    then calculates the SHA512 hash value,
    and finally returns the hexadecimal representation of the digest.

    .. inheritance-diagram:: JsonSha512HexHashMixin
        :parts: 1
    """

    __hash_config__ = HashConfig(
        algorithm="sha512", serializer=lambda x: json.dumps(x).encode(), decoder=lambda x: x.hexdigest()
    )


class JsonSha512Base64HashMixin(AbstractHashMixin):
    """
    Serializes the function name, source code, and arguments using the :mod:`json` module,
    then calculates the SHA512 hash value,
    and finally returns the base64 encoded digest.

    .. inheritance-diagram:: JsonSha512Base64HashMixin
        :parts: 1
    """

    __hash_config__ = HashConfig(
        algorithm="sha512",
        serializer=lambda x: json.dumps(x).encode(),
        decoder=b64digest,
    )


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

    __hash_config__ = HashConfig(algorithm="md5", serializer=pickle.dumps, decoder=lambda x: x.hexdigest())


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

    __hash_config__ = HashConfig(algorithm="sha1", serializer=pickle.dumps, decoder=lambda x: x.hexdigest())


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

    __hash_config__ = HashConfig(algorithm="sha256", serializer=pickle.dumps, decoder=lambda x: x.hexdigest())


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

    __hash_config__ = HashConfig(algorithm="sha512", serializer=pickle.dumps, decoder=lambda x: x.hexdigest())


class PickleSha512Base64HashMixin(AbstractHashMixin):
    """
    Serializes the function name, source code, and arguments using the :mod:`pickle` module,
    then calculates the SHA512 hash value,
    and finally returns the base64 encoded digest.

    .. inheritance-diagram:: PickleSha512Base64HashMixin
        :parts: 1
    """

    __hash_config__ = HashConfig(algorithm="sha512", serializer=pickle.dumps, decoder=b64digest)
