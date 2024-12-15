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
    Overwrite the class variable :func:`hash_config` to define algorithm and serializer.

    Example::

        class Md5JsonHashMixin(AbstractHashMixin):
            hash_config = HashConfig(algorithm="md5", serializer=lambda x: json.dumps(x).encode())
    """

    hash_config: HashConfig

    def calc_hash(
        self, f: Optional[Callable] = None, args: Optional[Sequence] = None, kwds: Optional[Mapping[str, Any]] = None
    ) -> KeyT:
        conf = self.hash_config
        if not callable(f):
            raise TypeError(f"Can not calculate hash for {f=}")  # pragma: no cover
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


def _hexdigest(x: _Hash):
    return x.hexdigest()


def _json_dump_bytes(x):
    return json.dumps(x).encode()


class JsonMd5HashMixin(AbstractHashMixin):
    hash_config = HashConfig(algorithm="md5", serializer=_json_dump_bytes)


class JsonMd5HexHashMixin(AbstractHashMixin):
    hash_config = HashConfig(algorithm="md5", serializer=_json_dump_bytes, decoder=_hexdigest)


class JsonSha1HashMixin(AbstractHashMixin):
    hash_config = HashConfig(algorithm="sha1", serializer=_json_dump_bytes)


class JsonSha1HexHashMixin(AbstractHashMixin):
    hash_config = HashConfig(algorithm="sha1", serializer=_json_dump_bytes, decoder=_hexdigest)


class JsonMd5Base64HashMixin(AbstractHashMixin):
    hash_config = HashConfig(algorithm="md5", serializer=_json_dump_bytes, decoder=base64_hash_digest)


class JsonSha1Base64HashMixin(AbstractHashMixin):
    hash_config = HashConfig(algorithm="sha1", serializer=_json_dump_bytes, decoder=base64_hash_digest)


class PickleMd5HashMixin(AbstractHashMixin):
    hash_config = HashConfig(algorithm="md5", serializer=pickle.dumps)


class PickleMd5HexHashMixin(AbstractHashMixin):
    hash_config = HashConfig(algorithm="md5", serializer=pickle.dumps, decoder=_hexdigest)


class PickleMd5Base64HashMixin(AbstractHashMixin):
    hash_config = HashConfig(algorithm="md5", serializer=pickle.dumps, decoder=base64_hash_digest)


class PickleSha1HashMixin(AbstractHashMixin):
    hash_config = HashConfig(algorithm="sha1", serializer=pickle.dumps)


class PickleSha1HexHashMixin(AbstractHashMixin):
    hash_config = HashConfig(algorithm="sha1", serializer=pickle.dumps, decoder=_hexdigest)


class PickleSha1Base64HashMixin(AbstractHashMixin):
    hash_config = HashConfig(algorithm="sha1", serializer=pickle.dumps, decoder=base64_hash_digest)
