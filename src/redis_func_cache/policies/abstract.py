from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Iterable, Mapping, Optional, Sequence, Tuple, TypeVar

from ..utils import read_lua_file

if TYPE_CHECKING:  # pragma: no cover
    from weakref import CallableProxyType

    from redis.commands.core import Script
    from redis.typing import EncodableT, EncodedT, KeyT

    from ..cache import RedisFuncCache

    UserFunctionT = TypeVar("UserFunctionT", bound=Callable)
    SerializerT = Callable[[Any], EncodedT]
    DeserializerT = Callable[[EncodedT], Any]


__all__ = ("AbstractPolicy",)


class AbstractPolicy:
    __key__: str
    __scripts__: Tuple[str, str]

    def __init__(self, cache: CallableProxyType[RedisFuncCache]):
        self._cache = cache
        self._lua_scripts: Optional[Tuple[Script, Script]] = None

    @property
    def cache(self) -> RedisFuncCache:
        """It's in fact a `weakref` proxy object, returned by :func:`weakref.proxy`.

        Here we type it as a :cls:`RedisFuncCache` to make a better hint.
        :mod:`weakref` is not a good idea.
        """
        return self._cache  # type: ignore

    def read_lua_scripts(self) -> Tuple[str, str]:
        return read_lua_file(self.__scripts__[0]), read_lua_file(self.__scripts__[1])

    @property
    def lua_scripts(self) -> Tuple[Script, Script]:
        if self._lua_scripts is None:
            script_texts = self.read_lua_scripts()
            rc = self.cache.get_client()
            self._lua_scripts = rc.register_script(script_texts[0]), rc.register_script(script_texts[1])
        return self._lua_scripts

    def purge(self) -> Optional[int]:
        raise NotImplementedError()  # pragma: no cover

    def get_size(self) -> int:
        raise NotImplementedError()  # pragma: no cover

    @property
    def size(self) -> int:
        return self.get_size()

    def calc_keys(
        self, f: Optional[Callable] = None, args: Optional[Sequence] = None, kwds: Optional[Mapping[str, Any]] = None
    ) -> Tuple[KeyT, KeyT]:
        raise NotImplementedError()  # pragma: no cover

    def calc_hash(
        self, f: Optional[Callable] = None, args: Optional[Sequence] = None, kwds: Optional[Mapping[str, Any]] = None
    ) -> KeyT:
        raise NotImplementedError()  # pragma: no cover

    def calc_ext_args(
        self, f: Optional[Callable] = None, args: Optional[Sequence] = None, kwds: Optional[Mapping[str, Any]] = None
    ) -> Optional[Iterable[EncodableT]]:
        return None
