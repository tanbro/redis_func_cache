"""Base class for single-pair cache."""

import json

from .abstract import AbstractHashMixin

__all__ = ("Md5HashMixin", "Md5JsonHashMixin")


class Md5HashMixin(AbstractHashMixin):
    __algorithm__ = "md5"


class Md5JsonHashMixin(Md5HashMixin):
    __serializer__ = lambda x: json.dumps(x).encode()  # noqa: E731
