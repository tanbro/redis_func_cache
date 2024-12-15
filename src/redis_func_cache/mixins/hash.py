from __future__ import annotations

import hashlib
import json
import pickle
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Mapping, Optional, Sequence

if TYPE_CHECKING:  # pragma: no cover
    from hashlib import _Hash

    from redis.typing import KeyT


from ..utils import base64_hash_digest, get_fullname, get_source

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
    """Configurator for :cls:`AbstractHashMixin`"""

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

    **Do NOT use the mixin class directory.**
    Overwrite the class variable :func:`__hash_config__` to define algorithm and serializer.

    Example::

        class Md5JsonHashMixin(AbstractHashMixin):
            __hash_config__ = HashConfig(algorithm="md5", serializer=lambda x: json.dumps(x).encode())
    """

    __hash_config__: HashConfig
    """Configure of how to calculate hash for a function."""

    def calc_hash(
        self, f: Optional[Callable] = None, args: Optional[Sequence] = None, kwds: Optional[Mapping[str, Any]] = None
    ) -> KeyT:
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
    __hash_config__ = HashConfig(algorithm="md5", serializer=json_dump_to_bytes)


class JsonMd5HexHashMixin(AbstractHashMixin):
    __hash_config__ = HashConfig(algorithm="md5", serializer=json_dump_to_bytes, decoder=hexdigest)


class JsonMd5Base64HashMixin(AbstractHashMixin):
    __hash_config__ = HashConfig(algorithm="md5", serializer=json_dump_to_bytes, decoder=base64_hash_digest)


class JsonSha1HashMixin(AbstractHashMixin):
    __hash_config__ = HashConfig(algorithm="sha1", serializer=json_dump_to_bytes)


class JsonSha1HexHashMixin(AbstractHashMixin):
    __hash_config__ = HashConfig(algorithm="sha1", serializer=json_dump_to_bytes, decoder=hexdigest)


class JsonSha1Base64HashMixin(AbstractHashMixin):
    __hash_config__ = HashConfig(algorithm="sha1", serializer=json_dump_to_bytes, decoder=base64_hash_digest)


class PickleMd5HashMixin(AbstractHashMixin):
    __hash_config__ = HashConfig(algorithm="md5", serializer=pickle.dumps)


class PickleMd5HexHashMixin(AbstractHashMixin):
    __hash_config__ = HashConfig(algorithm="md5", serializer=pickle.dumps, decoder=hexdigest)


class PickleMd5Base64HashMixin(AbstractHashMixin):
    __hash_config__ = HashConfig(algorithm="md5", serializer=pickle.dumps, decoder=base64_hash_digest)


class PickleSha1HashMixin(AbstractHashMixin):
    __hash_config__ = HashConfig(algorithm="sha1", serializer=pickle.dumps)


class PickleSha1HexHashMixin(AbstractHashMixin):
    __hash_config__ = HashConfig(algorithm="sha1", serializer=pickle.dumps, decoder=hexdigest)


class PickleSha1Base64HashMixin(AbstractHashMixin):
    __hash_config__ = HashConfig(algorithm="sha1", serializer=pickle.dumps, decoder=base64_hash_digest)
