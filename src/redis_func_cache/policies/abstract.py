from __future__ import annotations

import weakref
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Callable, Iterable, Mapping, Optional, Sequence, Tuple, Union

from redis.commands.core import AsyncScript, Script

from ..utils import clean_lua_script, read_lua_file

if TYPE_CHECKING:  # pragma: no cover
    from redis.typing import EncodableT, KeyT, ScriptTextT

    from ..cache import RedisFuncCache


__all__ = ("AbstractPolicy",)


class AbstractPolicy(ABC):
    """
    Abstract base class for cache eviction policies used by :class:`RedisFuncCache`.

    Subclasses **MUST** implement:
      - :meth:`calc_keys`
      - :meth:`calc_hash`

    Optionally, subclasses may define:
      - __key__: A string component used in Redis key naming.
      - __scripts__: A tuple of two Lua script filenames (get, put).

    The use of :attr:`__key__` or :attr:`__scripts__` depends on the implementation of :meth:`calc_keys` and :meth:`calc_hash`.
    """

    __key__: str
    __scripts__: Tuple[str, str]

    def __init__(self, cache: weakref.CallableProxyType[RedisFuncCache]):
        """
        Args:
            cache: A weakref proxy to the :class:`RedisFuncCache` instance using this policy.
        """
        self._cache = cache
        self._lua_scripts: Union[None, Tuple[Script, Script], Tuple[AsyncScript, AsyncScript]] = None

    @property
    def cache(self) -> RedisFuncCache:
        """
        Returns:
            The :class:`RedisFuncCache` instance (via weakref proxy) that uses this policy.
        """
        return self._cache  # type: ignore

    @abstractmethod
    def calc_keys(
        self, f: Optional[Callable] = None, args: Optional[Sequence] = None, kwds: Optional[Mapping[str, Any]] = None
    ) -> Tuple[str, str]:
        """
        Calculate the Redis key pair for caching.

        Args:
            f: The function being cached.
            args: Positional arguments.
            kwds: Keyword arguments.

        Returns:
            Tuple of two Redis key names (e.g., for set and hash).
        """
        raise NotImplementedError()

    @abstractmethod
    def calc_hash(
        self, f: Optional[Callable] = None, args: Optional[Sequence] = None, kwds: Optional[Mapping[str, Any]] = None
    ) -> KeyT:
        """
        Calculate a unique hash for the function and its arguments.

        Args:
            f: The function being cached.
            args: Positional arguments.
            kwds: Keyword arguments.

        Returns:
            The calculated hash value.
        """
        raise NotImplementedError()

    def calc_ext_args(
        self, f: Optional[Callable] = None, args: Optional[Sequence] = None, kwds: Optional[Mapping[str, Any]] = None
    ) -> Optional[Iterable[EncodableT]]:
        """
        Optionally calculate extra arguments to pass to the Lua script.

        Args:
            f: The function being cached.
            args: Positional arguments.
            kwds: Keyword arguments.

        Returns:
            Iterable of extra encodable arguments, or None.
        """
        return None

    def read_lua_scripts(self) -> Tuple[ScriptTextT, ScriptTextT]:
        """
        Read and clean the Lua scripts from package resources.

        Returns:
            Tuple of cleaned Lua script texts (get, put).
        """
        return (
            clean_lua_script(read_lua_file(self.__scripts__[0])),
            clean_lua_script(read_lua_file(self.__scripts__[1])),
        )

    @property
    def lua_scripts(self) -> Union[Tuple[Script, Script], Tuple[AsyncScript, AsyncScript]]:
        """
        Register and return Lua scripts as Redis Script/AsyncScript objects.

        Returns:
            Tuple of registered Script or AsyncScript objects.
        """
        if self._lua_scripts is None:
            script_texts = self.read_lua_scripts()
            self._lua_scripts = (
                self.cache.client.register_script(script_texts[0]),
                self.cache.client.register_script(script_texts[1]),
            )
        return self._lua_scripts

    def purge(self) -> int:
        """
        Purge the cache.

        Returns:
            Number of items removed (if implemented).

        Raises:
            NotImplementedError: If not implemented by subclass.
        """
        raise NotImplementedError()  # pragma: no cover

    async def apurge(self) -> int:
        """
        Asynchronously purge the cache.

        Returns:
            Number of items removed (if implemented).

        Raises:
            NotImplementedError: If not implemented by subclass.
        """
        raise NotImplementedError()  # pragma: no cover

    def get_size(self) -> int:
        """
        Get the number of items in the cache.

        Returns:
            The cache size.

        Raises:
            NotImplementedError: If not implemented by subclass.
        """
        raise NotImplementedError()  # pragma: no cover

    async def aget_size(self) -> int:
        """
        Asynchronously get the number of items in the cache.

        Returns:
            The cache size.

        Raises:
            NotImplementedError: If not implemented by subclass.
        """
        raise NotImplementedError()  # pragma: no cover
