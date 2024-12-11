"""Base class for single-pair cache."""

import json

from .abstract import AbstractHashMixin

__all__ = ("Sha1HashMixin", "Sha1JsonHashMixin")


class Sha1HashMixin(AbstractHashMixin):
    __algorithm__ = "sha1"


class Sha1JsonHashMixin(Sha1HashMixin):
    __serializer__ = lambda x: json.dumps(x).encode()  # noqa: E731
