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
    "JsonMd5Base64HashMixin",
    "JsonSha1HashMixin",
    "JsonSha1Base64HashMixin",
    "PickleMd5HashMixin",
    "PickleMd5Base64HashMixin",
    "PickleSha1HashMixin",
    "PickleSha1Base64HashMixin",
)


@dataclass(frozen=True)
class HashConfig:
    serializer: Callable[[Any], bytes]
    algorithm: str
    decoder: Callable[[_Hash], KeyT]


class AbstractHashMixin:
    """An abstract mixin class for hash function name, source code, and arguments.

    **Do NOT use the mixin class directory.**
    Overwrite the following class variables to define algorithm and serializer.

    *. `__algorithm__` is the name for hashing algorithm
    *. `__serializer__` is the serialize function

    The class call `__serializer__` to serialize function name, source code, and arguments into bytes,
    then use `__algorithm__` to calculate hash.

    Example::

        class Md5JsonHashMixin(AbstractHashMixin):
            __serializer__ = lambda x: json.dumps(x).encode()
            __algorithm__ = "md5"
    """

    __hash_config__: HashConfig

    def calc_hash(
        self, f: Optional[Callable] = None, args: Optional[Sequence] = None, kwds: Optional[Mapping[str, Any]] = None
    ) -> KeyT:
        conf = self.__hash_config__
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
        return conf.decoder(h)


def _hexdigest(x: _Hash):
    return x.hexdigest()


def _json_dump_bytes(x):
    return json.dumps(x).encode()


class PickleMd5HashMixin(AbstractHashMixin):
    __hash_config__ = HashConfig(algorithm="md5", serializer=pickle.dumps, decoder=_hexdigest)


class JsonMd5HashMixin(AbstractHashMixin):
    __hash_config__ = HashConfig(algorithm="md5", serializer=_json_dump_bytes, decoder=_hexdigest)


class PickleSha1HashMixin(AbstractHashMixin):
    __hash_config__ = HashConfig(algorithm="sha1", serializer=pickle.dumps, decoder=_hexdigest)


class JsonSha1HashMixin(AbstractHashMixin):
    __hash_config__ = HashConfig(algorithm="sha1", serializer=_json_dump_bytes, decoder=_hexdigest)


class PickleMd5Base64HashMixin(AbstractHashMixin):
    __hash_config__ = HashConfig(algorithm="md5", serializer=pickle.dumps, decoder=base64_hash_digest)


class JsonMd5Base64HashMixin(AbstractHashMixin):
    __hash_config__ = HashConfig(algorithm="md5", serializer=_json_dump_bytes, decoder=base64_hash_digest)


class PickleSha1Base64HashMixin(AbstractHashMixin):
    __hash_config__ = HashConfig(algorithm="sha1", serializer=pickle.dumps, decoder=base64_hash_digest)


class JsonSha1Base64HashMixin(AbstractHashMixin):
    __hash_config__ = HashConfig(algorithm="sha1", serializer=_json_dump_bytes, decoder=base64_hash_digest)
