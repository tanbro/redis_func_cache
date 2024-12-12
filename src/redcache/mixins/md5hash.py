import json
import pickle

from .abstract import AbstractHashMixin

__all__ = ("Md5PickleMixin", "Md5JsonMixin")


class Md5PickleMixin(AbstractHashMixin):
    __algorithm__ = "md5"
    __serializer__ = pickle.dumps


class Md5JsonMixin(AbstractHashMixin):
    __algorithm__ = "md5"
    __serializer__ = lambda x: json.dumps(x).encode()  # noqa: E731
