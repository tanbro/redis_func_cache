from __future__ import annotations

import weakref
from typing import TYPE_CHECKING, Any, Callable, Iterable, Mapping, Optional, Sequence, Tuple, TypeVar, Union

from ..utils import read_lua_file

if TYPE_CHECKING:  # pragma: no cover
    from redis.commands.core import AsyncScript, Script
    from redis.typing import EncodableT, EncodedT, KeyT, ScriptTextT

    from ..cache import RedisFuncCache

    UserFunctionT = TypeVar("UserFunctionT", bound=Callable)
    SerializerT = Callable[[Any], EncodedT]
    DeserializerT = Callable[[EncodedT], Any]


__all__ = ("AbstractPolicy",)


class AbstractPolicy:
    """An abstract policy class for :class:`.RedisFuncCache`.

    Subclasses **MUST** implement the following methods:

    - :meth:`calc_keys`
    - :meth:`calc_hash`

    and shall optional define the following attributes:

    - ``__key__``: A component of the Redis key pair used by this policy.
    - ``__scripts__``: A tuple containing two strings; the first string is the script for ``get``, and the second string is the script for ``put``.

    Whether to use it is determined by how :meth:`calc_keys` and :meth:`calc_hash` are implemented.
    """

    __key__: str
    __scripts__: Tuple[str, str]

    def __init__(self, cache: weakref.CallableProxyType[RedisFuncCache]):
        """
        Args:
            cache: A ProxyType instance of :class:`.RedisFuncCache` object which uses the policy.
        """
        self._cache = cache
        self._lua_scripts: Union[None, Tuple[Script, Script], Tuple[AsyncScript, AsyncScript]] = None

    @property
    def cache(self) -> RedisFuncCache:
        """Proxy to the cache object who uses this policy.

        It's in fact a :mod:`weakref` proxy object, returned by :func:`weakref.proxy`.

        Here we type it as a :class:`RedisFuncCache` to make a better hint.
        """
        return self._cache  # type: ignore

    def calc_keys(
        self, f: Optional[Callable] = None, args: Optional[Sequence] = None, kwds: Optional[Mapping[str, Any]] = None
    ) -> Tuple[KeyT, KeyT]:
        """Calculate the names of the key pair used in the Redis data structure for the cache.

        This method is responsible for calculating the key names used in the Redis data structure for caching.
        It takes an optional function, arguments, and keyword arguments as input, and returns a tuple containing two key names.

        .. important::
            - This method is not implemented in the base class.
            - Subclasses **MUST** implement this method.
              This is because different caching strategies may require different key naming rules, so this method is designed to be overridden by subclasses.

        Args:
            f: The function for which the cache keys are being calculated.
            args: The positional arguments of the function.
            kwds: The keyword arguments of the function.

        Returns:
            A pair of key names, used for identifying and accessing the cache in Redis.
        """
        raise NotImplementedError()  # pragma: no cover

    def calc_hash(
        self, f: Optional[Callable] = None, args: Optional[Sequence] = None, kwds: Optional[Mapping[str, Any]] = None
    ) -> KeyT:
        """Calculate the hash for a given function and its arguments.

        This method is intended to generate a unique hash based on the input function and its parameters.
        If any of the inputs are None, it indicates that the parameter was not provided.

        .. important::
            - This method is not implemented in the base class.
            - Subclasses **MUST** implement this method.

        Args:
            f: The function for which the hash is to be calculated. Defaults to None.
            args: Positional arguments for the function. Defaults to None.
            kwds: Keyword arguments for the function. Defaults to None.

        Returns:
            The calculated hash value.

        """
        raise NotImplementedError()  # pragma: no cover

    def calc_ext_args(
        self, f: Optional[Callable] = None, args: Optional[Sequence] = None, kwds: Optional[Mapping[str, Any]] = None
    ) -> Optional[Iterable[EncodableT]]:
        """
        Calculate and return the extended arguments for a given function.

        This method is designed to dynamically calculate the extended arguments required for a function call, based on the function itself, its arguments, and keyword arguments.
        It supports scenarios where the function, its arguments, or its keyword arguments may not be provided.

        The extra arguments are expected to be encodable types and will be passed to the Lua script at the tail of its ``args`` parameter.

        Subclass my override this method to provide custom handling for specific functions or scenarios.

        Args:
            f: The function for which to calculate the extended arguments. May be None.
            args: Positional arguments for the function. May be None.
            kwds: Keyword arguments for the function. May be None.

        Returns:
            The calculated extended arguments, which may include any encodable type.
            If no extended arguments can be calculated based on the provided inputs, and nothing will be appended to the Lua script's ``args`` parameter.

        .. note::
            - By default, it returns ``None``, indicating no extra arguments.
            - This method is designed to handle optional inputs, allowing for flexible use cases where the function or its arguments may not be specified.
            - The return type indicates a possible collection of encodable types, accommodating a wide range of outputs depending on the function and inputs provided.
        """
        return None

    def read_lua_scripts(self) -> Tuple[ScriptTextT, ScriptTextT]:
        """Read the Lua scripts from the package resources."""
        return read_lua_file(self.__scripts__[0]), read_lua_file(self.__scripts__[1])

    @property
    def lua_scripts(self) -> Union[Tuple[Script, Script], Tuple[AsyncScript, AsyncScript]]:
        """Read the Lua scripts from the package resources, then create and return a pair of :class:`redis.commands.core.Script` or :class:`redis.commands.core.AsyncScript` objects.

        - When :meth:`cache` property has a synchronous Redis client, it will return a pair of :class:`redis.commands.core.Script` objects.
        - When :meth:`cache` property has an asynchronous Redis client, it will return a pair of :class:`redis.commands.core.AsyncScript` objects.
        """
        if self._lua_scripts is None:
            script_texts = self.read_lua_scripts()
            self._lua_scripts = (
                self.cache.client.register_script(script_texts[0]),
                self.cache.client.register_script(script_texts[1]),
            )
        return self._lua_scripts

    def purge(self) -> int:
        """Purge the cache.

        .. note::
            - This method is not implemented in the base class.
            - Subclasses can optionally implement this method.
        """
        raise NotImplementedError()  # pragma: no cover

    async def apurge(self) -> int:
        """Asynchronously purge the cache."""
        raise NotImplementedError()  # pragma: no cover

    def size(self) -> int:
        """Return the number of items in the cache.

        .. note::
            - This method is not implemented in the base class.
            - Subclasses can optionally implement this method.

        Since the size is fetched from Redis, it involves I/O operations.
        Therefore, this is a method rather than a property.
        """
        raise NotImplementedError()  # pragma: no cover

    async def asize(self) -> int:
        """Asynchronously return the number of items in the cache."""
        raise NotImplementedError()  # pragma: no cover
