"""Hashers: the *hash* dimension of a policy.

A :class:`Hasher` computes the sub-key under which a call's result is stored —
the member of the index structure (ZSET/SET) and the field name of the hash
map. It is one of the three orthogonal components composed into a
:class:`~redis_func_cache.policies.Policy`:

- :class:`~redis_func_cache.keying.Keying` — how Redis keys are named
- :class:`Hasher` — how each call is hashed to a sub-key
- :class:`~redis_func_cache.scripts.Scripts` — which Lua scripts run
  and how they talk to Redis

Define a custom hasher by subclassing :class:`Hasher` and setting
:attr:`__hash_config__`, e.g. to stop hashing function bytecode for
cross-version cache compatibility::

    from dataclasses import replace

    from redis_func_cache.hashing import HashConfig, JsonMd5Hasher


    class StableJsonMd5Hasher(JsonMd5Hasher):
        __hash_config__ = replace(JsonMd5Hasher.__hash_config__, use_bytecode=False)

.. versionchanged:: 1.0
    Replaces the ``mixins.hash`` mixin classes. Hashers are plain components
    composed into a :class:`~redis_func_cache.policies.Policy` instead
    of being woven in via multiple inheritance.
"""

from __future__ import annotations

import json
import pickle
from abc import ABC
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .fingerprint import hash_fingerprint
from .typing import HashValueT
from .utils import b64digest

if TYPE_CHECKING:  # pragma: no cover
    from hashlib import _Hash as HashT

__all__ = (
    "PICKLE_MD5_HASHER",
    "HashConfig",
    "Hasher",
    "JsonMd5Base64Hasher",
    "JsonMd5Hasher",
    "JsonMd5HexHasher",
    "JsonSha1Base64Hasher",
    "JsonSha1Hasher",
    "JsonSha1HexHasher",
    "JsonSha256Base64Hasher",
    "JsonSha256Hasher",
    "JsonSha256HexHasher",
    "JsonSha512Base64Hasher",
    "JsonSha512Hasher",
    "JsonSha512HexHasher",
    "PickleMd5Base64Hasher",
    "PickleMd5Hasher",
    "PickleMd5HexHasher",
    "PickleSha1Base64Hasher",
    "PickleSha1Hasher",
    "PickleSha1HexHasher",
    "PickleSha256Base64Hasher",
    "PickleSha256Hasher",
    "PickleSha256HexHasher",
    "PickleSha512Base64Hasher",
    "PickleSha512Hasher",
    "PickleSha512HexHasher",
    "make_hasher",
)


@dataclass(frozen=True)
class HashConfig:
    """Configuration for a :class:`Hasher`."""

    algorithm: str
    """name for hashing algorithm

    The name must be supported by :mod:`hashlib`.
    """
    serializer: Callable[[Any], bytes]
    """function to serialize function positional and keyword arguments."""
    decoder: Callable[[HashT], HashValueT] | None = None
    """function to decode hash digest to member of a sorted/unsorted set and also field name of a hash map in redis.

    Default is :data:`None`, means no decoding and to use the raw digest bytes directly.
    """
    use_bytecode: bool = True
    """whether to use bytecode of the function to calculate hash.

    .. versionadded:: 0.5
    """


class Hasher(ABC):
    """Compute the sub-key a call's result is stored under.

    The result is used as the member of the index structure and the field name
    of the hash map in Redis.

    Subclass and override :attr:`__hash_config__` to define the algorithm,
    serializer and decoder.
    """

    __hash_config__: HashConfig

    def calc_hash(
        self,
        fn: Callable | None = None,
        args: tuple[Any, ...] | None = None,
        kwds: dict[str, Any] | None = None,
    ) -> HashValueT:
        """Calculate the hash value of the function and its arguments.

        Args:
            fn: The function to calculate hash for.
            args: The positional arguments of the function.
            kwds: The keyword arguments of the function.

        Returns:
            The hash value of the function.

        Raises:
            TypeError: If the function is not callable.
        """
        if fn is None:
            raise TypeError("Can not calculate hash for None")
        conf = self.__hash_config__
        h = hash_fingerprint(conf.algorithm, conf.use_bytecode, fn).copy()
        if args is not None:
            h.update(conf.serializer(args))
        if kwds is not None:
            h.update(conf.serializer(kwds))
        if conf.decoder is None:
            return h.digest()
        return conf.decoder(h)


JSON_SERIALIZER = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":")).encode()
HEX_DIGEST_DECODER = lambda x: x.hexdigest()


def make_hasher(name: str, hash_config: HashConfig) -> type[Hasher]:
    """Create a :class:`Hasher` subclass from a :class:`HashConfig`.

    A convenience for one-off combinations that are not worth a hand-written
    class. The built-in presets are explicit classes instead.

    Args:
        name: Name of the generated class.
        hash_config: Configuration for the generated class's :attr:`__hash_config__`.

    Returns:
        A new :class:`Hasher` subclass; each call returns a fresh class. Type
        checks should target :class:`Hasher` rather than a particular call's result.

    Note:
        Hash values are stable only within a single library version. Changing the
        serializer or decoder output changes cache keys and invalidates existing entries.
    """
    return type(name, (Hasher,), {"__hash_config__": hash_config})


class JsonMd5Hasher(Hasher):
    """Serialize with :mod:`json`, hash with MD5, return the raw digest bytes."""

    __hash_config__ = HashConfig(algorithm="md5", serializer=JSON_SERIALIZER)


class JsonMd5HexHasher(Hasher):
    """Serialize with :mod:`json`, hash with MD5, return the hex digest."""

    __hash_config__ = HashConfig(algorithm="md5", serializer=JSON_SERIALIZER, decoder=HEX_DIGEST_DECODER)


class JsonMd5Base64Hasher(Hasher):
    """Serialize with :mod:`json`, hash with MD5, return the base64 digest."""

    __hash_config__ = HashConfig(algorithm="md5", serializer=JSON_SERIALIZER, decoder=b64digest)


class JsonSha1Hasher(Hasher):
    """Serialize with :mod:`json`, hash with SHA1, return the raw digest bytes."""

    __hash_config__ = HashConfig(algorithm="sha1", serializer=JSON_SERIALIZER)


class JsonSha1HexHasher(Hasher):
    """Serialize with :mod:`json`, hash with SHA1, return the hex digest."""

    __hash_config__ = HashConfig(algorithm="sha1", serializer=JSON_SERIALIZER, decoder=HEX_DIGEST_DECODER)


class JsonSha1Base64Hasher(Hasher):
    """Serialize with :mod:`json`, hash with SHA1, return the base64 digest."""

    __hash_config__ = HashConfig(algorithm="sha1", serializer=JSON_SERIALIZER, decoder=b64digest)


class JsonSha256Hasher(Hasher):
    """Serialize with :mod:`json`, hash with SHA256, return the raw digest bytes."""

    __hash_config__ = HashConfig(algorithm="sha256", serializer=JSON_SERIALIZER)


class JsonSha256HexHasher(Hasher):
    """Serialize with :mod:`json`, hash with SHA256, return the hex digest."""

    __hash_config__ = HashConfig(algorithm="sha256", serializer=JSON_SERIALIZER, decoder=HEX_DIGEST_DECODER)


class JsonSha256Base64Hasher(Hasher):
    """Serialize with :mod:`json`, hash with SHA256, return the base64 digest."""

    __hash_config__ = HashConfig(algorithm="sha256", serializer=JSON_SERIALIZER, decoder=b64digest)


class JsonSha512Hasher(Hasher):
    """Serialize with :mod:`json`, hash with SHA512, return the raw digest bytes."""

    __hash_config__ = HashConfig(algorithm="sha512", serializer=JSON_SERIALIZER)


class JsonSha512HexHasher(Hasher):
    """Serialize with :mod:`json`, hash with SHA512, return the hex digest."""

    __hash_config__ = HashConfig(algorithm="sha512", serializer=JSON_SERIALIZER, decoder=HEX_DIGEST_DECODER)


class JsonSha512Base64Hasher(Hasher):
    """Serialize with :mod:`json`, hash with SHA512, return the base64 digest."""

    __hash_config__ = HashConfig(algorithm="sha512", serializer=JSON_SERIALIZER, decoder=b64digest)


class PickleMd5Hasher(Hasher):
    """Serialize with :mod:`pickle`, hash with MD5, return the raw digest bytes.

    This is the hasher every built-in policy uses.
    """

    __hash_config__ = HashConfig(algorithm="md5", serializer=pickle.dumps)


class PickleMd5HexHasher(Hasher):
    """Serialize with :mod:`pickle`, hash with MD5, return the hex digest."""

    __hash_config__ = HashConfig(algorithm="md5", serializer=pickle.dumps, decoder=HEX_DIGEST_DECODER)


class PickleMd5Base64Hasher(Hasher):
    """Serialize with :mod:`pickle`, hash with MD5, return the base64 digest."""

    __hash_config__ = HashConfig(algorithm="md5", serializer=pickle.dumps, decoder=b64digest)


class PickleSha1Hasher(Hasher):
    """Serialize with :mod:`pickle`, hash with SHA1, return the raw digest bytes."""

    __hash_config__ = HashConfig(algorithm="sha1", serializer=pickle.dumps)


class PickleSha1HexHasher(Hasher):
    """Serialize with :mod:`pickle`, hash with SHA1, return the hex digest."""

    __hash_config__ = HashConfig(algorithm="sha1", serializer=pickle.dumps, decoder=HEX_DIGEST_DECODER)


class PickleSha1Base64Hasher(Hasher):
    """Serialize with :mod:`pickle`, hash with SHA1, return the base64 digest."""

    __hash_config__ = HashConfig(algorithm="sha1", serializer=pickle.dumps, decoder=b64digest)


class PickleSha256Hasher(Hasher):
    """Serialize with :mod:`pickle`, hash with SHA256, return the raw digest bytes."""

    __hash_config__ = HashConfig(algorithm="sha256", serializer=pickle.dumps)


class PickleSha256HexHasher(Hasher):
    """Serialize with :mod:`pickle`, hash with SHA256, return the hex digest."""

    __hash_config__ = HashConfig(algorithm="sha256", serializer=pickle.dumps, decoder=HEX_DIGEST_DECODER)


class PickleSha256Base64Hasher(Hasher):
    """Serialize with :mod:`pickle`, hash with SHA256, return the base64 digest."""

    __hash_config__ = HashConfig(algorithm="sha256", serializer=pickle.dumps, decoder=b64digest)


class PickleSha512Hasher(Hasher):
    """Serialize with :mod:`pickle`, hash with SHA512, return the raw digest bytes."""

    __hash_config__ = HashConfig(algorithm="sha512", serializer=pickle.dumps)


class PickleSha512HexHasher(Hasher):
    """Serialize with :mod:`pickle`, hash with SHA512, return the hex digest."""

    __hash_config__ = HashConfig(algorithm="sha512", serializer=pickle.dumps, decoder=HEX_DIGEST_DECODER)


class PickleSha512Base64Hasher(Hasher):
    """Serialize with :mod:`pickle`, hash with SHA512, return the base64 digest."""

    __hash_config__ = HashConfig(algorithm="sha512", serializer=pickle.dumps, decoder=b64digest)


#: The hasher every built-in policy uses: pickle-serialized arguments, MD5 digest.
PICKLE_MD5_HASHER = PickleMd5Hasher()
