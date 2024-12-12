import json
import pickle

from .abstract import AbstractHashMixin

__all__ = ("Sha1PickleMixin", "Sha1JsonMixin")


class Sha1PickleMixin(AbstractHashMixin):
    __algorithm__ = "sha1"
    __serializer__ = pickle.dumps


class Sha1JsonMixin(AbstractHashMixin):
    __algorithm__ = "sha1"
    __serializer__ = lambda x: json.dumps(x).encode()  # noqa: E731
