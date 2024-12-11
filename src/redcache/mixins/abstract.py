import hashlib
import pickle
from typing import Any, Callable, Mapping, Optional, Sequence

from ..utils import get_fullname, get_source

__all__ = ("AbstractHashMixin",)


class AbstractHashMixin:
    """An abstract mixin class for hash function name, source code, and arguments.

    **Do NOT use the mixin class directory.**
    Overwrite the following class variables to define algorithm and serializer.

    *. `__algorithm__` is the algorithm name. It's required
    *. `__serializer__` is the serialize function. It's optional, default is :func"`pickle.dumps`.

    The class call `__serializer__` to serialize function name, source code, and arguments into bytes,
    then use `__algorithm__` to calculate hash.

    Example::

        class JsonMd5FullHashMixin(AbstractHashMixin):
            __serializer__ = lambda x: json.dumps(x).encode()
            __algorithm__ = "md5"
    """

    __serializer__: Callable[[Any], bytes] = pickle.dumps
    __algorithm__: str

    def calculate_hash(
        self, f: Optional[Callable] = None, args: Optional[Sequence] = None, kwds: Optional[Mapping[str, Any]] = None
    ) -> str:
        if not callable(f):
            raise TypeError(f"Can not calculate hash for {f=}")
        h = hashlib.new(self.__algorithm__)
        h.update(get_fullname(f).encode())
        source = get_source(f)
        if source is not None:
            h.update(source.encode())
        if args is not None:
            h.update(self.__serializer__(args))
        if kwds is not None:
            h.update(self.__serializer__(kwds))
        return h.hexdigest()
