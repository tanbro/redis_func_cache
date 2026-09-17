from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from weakref import CallableProxyType

from redis.commands.core import AsyncScript, Script

from ..utils import clean_lua_script, read_lua_file

if TYPE_CHECKING:  # pragma: no cover
    from redis.typing import EncodableT, KeyT, ScriptTextT

    from ..cache import RedisFuncCache


__all__ = ("AbstractPolicy",)


class AbstractPolicy(ABC):
    """
    Abstract base class for cache eviction policies used by :class:`RedisFuncCache`.

    .. inheritance-diagram:: AbstractPolicy
        :parts: 1

    Subclasses **MUST** implement:
      - :meth:`calc_keys`
      - :meth:`calc_hash`

    Optionally, subclasses may define:
      - __key__: A string component used in Redis key naming.
      - __scripts__: A tuple of two Lua script filenames (get, put).

    The use of :attr:`__key__` or :attr:`__scripts__` depends on the implementation of :meth:`calc_keys` and :meth:`calc_hash`.
    """

    __key__: str
    __scripts__: tuple[str, str]

    def __init__(self) -> None:
        """
        Args:
            cache: Optional weakref proxy to the :class:`RedisFuncCache` instance using this policy.

        Note:
            The cache argument may be omitted when instantiating a policy. The
            `RedisFuncCache` will bind itself to the policy instance by setting
            this attribute to a weakref proxy during cache construction.
        """
        self._cache: CallableProxyType[RedisFuncCache] | None = None
        self._lua_scripts: tuple[Script, Script] | tuple[AsyncScript, AsyncScript] | None = None

    @property
    def cache(self) -> CallableProxyType[RedisFuncCache]:
        """
        Returns:
            The :class:`RedisFuncCache` instance (via weakref proxy) that uses this policy.
        """
        if self._cache is None:
            raise RuntimeError("Policy instance is not bound to a RedisFuncCache")
        return self._cache

    @abstractmethod
    def calc_keys(
        self,
        fn: Callable | None = None,
        args: tuple[Any, ...] | None = None,
        kwds: dict[str, Any] | None = None,
    ) -> tuple[str, str]:
        """
        Calculate the Redis key pair for caching.

        Args:
            f: The function being cached.
            args: Positional arguments.
            kwds: Keyword arguments.

        Returns:
            Tuple of two Redis key names (e.g., for set and hash).
        """
        raise NotImplementedError()  # pragma: no cover

    @abstractmethod
    def calc_hash(
        self,
        fn: Callable | None = None,
        args: tuple[Any, ...] | None = None,
        kwds: dict[str, Any] | None = None,
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
        raise NotImplementedError()  # pragma: no cover

    def calc_ext_args(
        self, f: Callable | None = None, args: Sequence | None = None, kwds: Mapping[str, Any] | None = None
    ) -> Iterable[EncodableT] | None:
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

    def read_lua_scripts(self) -> tuple[ScriptTextT, ScriptTextT]:
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
    def lua_scripts(self) -> tuple[Script, Script] | tuple[AsyncScript, AsyncScript]:
        """
        Register and return Lua scripts as Redis Script/AsyncScript objects.

        Returns:
            Tuple of registered Script or AsyncScript objects.
        """
        if self._lua_scripts is None:
            client = self.cache.get_client()
            script_texts = self.read_lua_scripts()
            self._lua_scripts = (
                client.register_script(script_texts[0]),
                client.register_script(script_texts[1]),
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
