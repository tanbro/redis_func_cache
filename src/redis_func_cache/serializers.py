"""Serializers: encode/decode pairs for cached values, keyed by name.

The :data:`SERIALIZERS` registry is populated at import time with the
always-available ``json`` and ``pickle`` serializers, plus any of ``dill``,
``bson``, ``msgpack``, ``cbor2``, ``yaml`` and ``cloudpickle`` whose packages
are installed (the corresponding optional extras).

Encoders produce :class:`bytes`; decoders accept whatever Redis returns
(:class:`~redis.typing.EncodedT` — ``bytes``, or ``str`` under
``decode_responses=True``; ``memoryview`` is handled defensively).
"""

from __future__ import annotations

import json
import pickle
from collections.abc import Callable
from typing import Any

from redis.typing import EncodedT

from .typing import SerializerName, is_module

__all__ = (
    "SERIALIZERS",
    "DeserializerT",
    "SerializerPairT",
    "SerializerSetterValueT",
    "SerializerT",
    "json_encode",
)

SerializerT = Callable[[Any], bytes]
"""Encode a value to bytes for storage in Redis."""
DeserializerT = Callable[[EncodedT], Any]
"""Decode stored bytes (or str / memoryview, defensively) back to a value."""
SerializerPairT = tuple[SerializerT, DeserializerT]
SerializerSetterValueT = SerializerName | SerializerPairT

try:  # pragma: no cover
    import dill  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    dill = None  # type: ignore[assignment]
try:  # pragma: no cover
    import bson  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    bson = None  # type: ignore[assignment]
try:  # pragma: no cover
    import cloudpickle  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    cloudpickle = None  # type: ignore[assignment]
try:  # pragma: no cover
    import msgpack  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    msgpack = None  # type: ignore[assignment]
try:
    import cbor2  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    cbor2 = None  # type: ignore[assignment]
try:  # pragma: no cover
    import yaml  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]
else:  # pragma: no cover
    if yaml.__with_libyaml__:  # pragma: no cover
        from yaml import CSafeDumper as YamlDumper  # type: ignore[import-not-found]
        from yaml import CSafeLoader as YamlLoader  # type: ignore[import-not-found]
    else:  # pragma: no cover
        from yaml import SafeDumper as YamlDumper  # type: ignore[assignment, import-not-found]
        from yaml import SafeLoader as YamlLoader  # type: ignore[assignment, import-not-found]

json_encode = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":")).encode()
_json_decode = lambda x: json.loads(bytes(x) if isinstance(x, memoryview) else x)

SERIALIZERS: dict[SerializerName, SerializerPairT] = {
    "json": (json_encode, _json_decode),
    "pickle": (lambda x: pickle.dumps(x), lambda x: pickle.loads(x)),
}
if is_module(dill):  # pragma: no cover
    _dill = dill

    def _dill_encode(x: Any) -> bytes:
        return _dill.dumps(x)

    def _dill_decode(x: EncodedT) -> Any:
        return _dill.loads(x)

    SERIALIZERS["dill"] = (_dill_encode, _dill_decode)

if is_module(bson):  # pragma: no cover
    _bson = bson

    def _bson_encode(x: Any) -> bytes:
        return _bson.encode({"": x})

    def _bson_decode(x: EncodedT) -> Any:
        return _bson.decode(x)[""]

    SERIALIZERS["bson"] = (_bson_encode, _bson_decode)

if is_module(msgpack):  # pragma: no cover
    _msgpack = msgpack

    def _msgpack_encode(x: Any) -> bytes:
        # use_bin_type=True: bytes -> msgpack bin, str -> msgpack str (msgpack spec 2.0)
        return _msgpack.packb(x, use_bin_type=True)

    def _msgpack_decode(x: EncodedT) -> Any:
        # raw=False: msgpack str -> python str, msgpack bin -> python bytes
        return _msgpack.unpackb(x, raw=False)

    SERIALIZERS["msgpack"] = (_msgpack_encode, _msgpack_decode)

if is_module(cbor2):  # pragma: no cover
    _cbor2 = cbor2

    def _cbor2_encode(x: Any) -> bytes:
        return _cbor2.dumps(x)

    def _cbor2_decode(x: EncodedT) -> Any:
        return _cbor2.loads(x)

    SERIALIZERS["cbor"] = (_cbor2_encode, _cbor2_decode)

if is_module(yaml):  # pragma: no cover
    _yaml = yaml

    def _yaml_encode(x: Any) -> bytes:
        return _yaml.dump(x, Dumper=YamlDumper).encode()  # pyright: ignore[reportPossiblyUnboundVariable]

    def _yaml_decode(x: EncodedT) -> Any:
        return _yaml.load(bytes(x) if isinstance(x, memoryview) else x, Loader=YamlLoader)  # pyright: ignore[reportPossiblyUnboundVariable]

    SERIALIZERS["yaml"] = (_yaml_encode, _yaml_decode)

if is_module(cloudpickle):  # pragma: no cover
    _cloudpickle = cloudpickle

    def _cloudpickle_encode(x: Any) -> bytes:
        return _cloudpickle.dumps(x)

    SERIALIZERS["cloudpickle"] = (_cloudpickle_encode, lambda x: pickle.loads(x))
