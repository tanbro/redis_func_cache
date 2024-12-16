# redis_func_cache

[![python-package](https://github.com/tanbro/redis_func_cache/actions/workflows/python-package.yml/badge.svg)](https://github.com/tanbro/redis_func_cache/actions/workflows/python-package.yml/badge.svg)
[![codecov](https://codecov.io/gh/tanbro/redis_func_cache/graph/badge.svg?token=BgeXJZdPbJ)](https://codecov.io/gh/tanbro/redis_func_cache)
[![readthedocs](https://readthedocs.org/projects/redis-func-cache/badge/)](https://readthedocs.org/projects/redis-func-cache/badge/)

`redis_func_cache` is a _Python_ library for caching function results in [Redis][], similar to the caching functionality provided by the standard library's [`functools`](https://docs.python.org/library/functools.html) module, which comes with some cache decorators, and is quite handy when we want to code something with memorization.
When we need to to cache functions return values distributed over multiple processes or machines, we can use [Redis][] as a backend.

The purpose of the project is to provide a simple and clean way to use [Redis][] as a backend for cache decorators.
It implements caches with _LRU_, _RR_, _FIFO_, _RR_ and _LFU_ eviction/replacement policies(<https://wikipedia.org/wiki/Cache_replacement_policies>).

> ❗ **Note**:\
> The project is still under development, and **DO NOT USE IT IN PRODUCTION**

## Install

- install from PyPI:

    ```bash
    pip install -U redis_func_cache
    ```

- install from source:

    ```bash
    git clone https://github.com/tanbro/redis_func_cache.git
    cd redis_func_cache
    python setup.py install
    ```

## Basic Usage

### First example

Using _LRU_ cache to decorate a recursive Fibonacci function:

```python
from redis import Redis
from redis_func_cache import RedisFuncCache, LruPolicy

redis_client = Redis(...)

lru_cache = RedisFuncCache("my-first-lru-cache", LruPolicy, redis_client)

@lru_cache
def fib(n):
    if n <= 1:
        return n
    if n == 2:
        return 1
    return fib(n - 1) + fib(n - 2)
```

In this example, we first create a [Redis][] client, then create a [`RedisFuncCache`][] instance with the [Redis][] client and [`LruPolicy`][] as it's arguments.
Next, we use the `@lru_cache` decorator to decorate the `fib` function.
This way, each computed result is cached, and subsequent calls with the same parameters retrieve the result directly from the cache, thereby improving performance.

It works almost the same like std-lib's `functools.lru_cache`, except that it uses [Redis][] as a backend, not local machine's memory.

If we browse keys in the [Redis][] database, we can find the cache keys and values.
For the [`LruPolicy`][], the keys are in a pair form.
The pair of keys' names look like:

- `redis_func_cache:my-first-lru-cache:lru:__main__:fib:0`

    The key(`0` suffix) is a sorted set stores functions invoking's hash and corresponding score/weight.

- `redis_func_cache:my-first-lru-cache:lru:__main__:fib:1`

    The key(`1` suffix) is a hash map. Each of it's key is the hash value of a function invoking, and value is the the return value of the function.

### Eviction policies

If want to use other eviction policies, you can specify another policy class as the second argument of [`RedisFuncCache`][].

For example, we use [`FifoPolicy`][] to implement a _FIFO_ cache:

```python
from redis_func_cache import FifoPolicy

fifo_cache = RedisFuncCache("my-cache-2", FifoPolicy, redis_client)

@fifo_cache
def func1(x):
    ...
```

Use [`RrPolicy`][] to implement a random-remove cache:

```python
from redis_func_cache import RrPolicy

rr_cache = RedisFuncCache("my-cache-3", RrPolicy, redis_client)

@rr_cache
def func2(x):
    ...
```

So far, the following policies are available:

- [`FifoPolicy`][]
- [`LfuPolicy`][]
- [`LruPolicy`][]
- [`MruPolicy`][]
- [`RrPolicy`][]

- **[`TLruPolicy`][]**

    > 💡**Tip**:\
    > It is a pseudo _LRU_ policy, not very serious/legitimate.
    > The policy removes the lowest member according to the timestamp of invocation, and does not completely ensure eviction of the least recently used item, since the timestamp may be inaccurate.
    > However, the policy is still **MOST RECOMMENDED** for common use. It is faster than the LRU policy and accurate enough for most cases.

> ℹ️ **Info**:\
> Explore source codes in `src/policies` for more details.

### Multiple [Redis][] key pairs

As described above, the cache keys are in a pair form. All decorated functions share the same two keys.
But some times, we may want to use different cache keys for different functions.

One solution is to use different [`RedisFuncCache`][] instances to decorate different functions.

Another way is to use a policy stores cache data in different [Redis][] key pairs for each function. There are several policies to do that out of the box.
For example, we can use [`TLruMultiplePolicy`][] for a _LRU_ cache that has multiple different [Redis][] key pairs to store return values of different functions, and each function has a standalone keys pair:

```python
from redis_func_cache import TLruMultiplePolicy

cache = RedisFuncCache("my-cache-4", TLruMultiplePolicy, redis_client)

@cache
def func1(x):
    ...

@cache
def func2(x):
    ...
```

In the example, [`TLruMultiplePolicy`][] inherits [`BaseMultiplePolicy`][] which implements how to store cache keys and values for each function.

When called, we can see such keys in the [Redis][] database:

- key pair for `func1`:

  - `redis_func_cache:my-cache-4:tlru-m:__main__:func1#<hash1>:0`
  - `redis_func_cache:my-cache-4:tlru-m:__main__:func1#<hash1>:1`

- key pair for `func2`:

  - `redis_func_cache:my-cache-4:tlru-m:__main__:func2#<hash2>:0`
  - `redis_func_cache:my-cache-4:tlru-m:__main__:func2#<hash2>:1`

where `<hash1>` and `<hash2>` are the hash values of the definitions of `func1` and `func2` respectively.

Policies that store cache in multiple [Redis][] key pairs are:

- [`FifoMultiplePolicy`][]
- [`LfuMultiplePolicy`][]
- [`LruMultiplePolicy`][]
- [`MruMultiplePolicy`][]
- [`RrMultiplePolicy`][]
- [`TLruMultiplePolicy`][]

### [Redis][] Cluster support

We already known that the library implements cache algorithms based on a pair of [Redis][] data structures, the two **MUST** be in a same [Redis][] node, or it will not work correctly.

While a [Redis][] cluster will distribute keys to different nodes based on the hash value of the key's name.

To ensure that two keys are placed in the same node, several cluster policies are provided. These policies use the `{...}` pattern in key names to achieve this.

For example, here we use a [`TLruClusterPolicy`][] to implement a cluster-aware _LRU_ cache:

```python
from redis_func_cache import TLruClusterPolicy

cache = RedisFuncCache("my-cluster-cache", TLruClusterPolicy, redis_client)

@cache
def my_func(x):
    ...
```

Then, the names of the key pair may be like:

- `redis_func_cache:{my-cluster-cache:tlru-c}:0`
- `redis_func_cache:{my-cluster-cache:tlru-c}:1`

Notice what is in `{...}`: the [Redis][] cluster will determine which node to store the key based on the `{...}` part rather than the entire key name string.

Policies that support cluster are:

- [`FifoClusterPolicy`][]
- [`LfuClusterPolicy`][]
- [`LruClusterPolicy`][]
- [`MruClusterPolicy`][]
- [`RrClusterPolicy`][]
- [`TLruClusterPolicy`][]

### [Redis][] Cluster support with multiple key pairs

Policies that support both cluster and store cache in multiple [Redis][] key pairs are:

- [`FifoClusterMultiplePolicy`][]
- [`LfuClusterMultiplePolicy`][]
- [`LruClusterMultiplePolicy`][]
- [`MruClusterMultiplePolicy`][]
- [`RrClusterMultiplePolicy`][]
- [`TLruClusterMultiplePolicy`][]

### Complex return types

The return value (de)serializer is default in [JSON][], which does not work with complex objects.

But, still, we can use [`pickle`][] to serialize the return value, by specifying `serializers` argument of [`RedisFuncCache`][]:

```python
import pickle

from redis_func_cache import RedisFuncCache, TLruPolicy


def redis_factory():
    ...


my_pickle_cache = RedisFuncCache(__name__, TLruPolicy, redis_factory, serializer=(pickle.dumps, pickle.loads))
```

> ⚠️ **Warning**:\
> [`pickle`][] is considered a security risk, and should not be used with runtime/version sensitive data. Use it cautiously and only when necessary.
> It's a good practice to only cache functions that return simple, [JSON][] serializable data types.

Other serialization ways are also workable, such as [simplejson](https://pypi.org/project/simplejson/), [cJSON](https://github.com/DaveGamble/cJSON), [msgpack](https://msgpack.org/), [cloudpickle](https://github.com/cloudpipe/cloudpickle), etc.

## Advanced Usage

### Custom key format

An instance of [`RedisFuncCache`][] calculate key pair names string by calling method `calc_keys` of it's policy.
There are four basic policies that implement respective kinds of key formats in the library:

- [`BaseSinglePolicy`][]: All functions share the same key pair, [Redis][] cluster is NOT supported.

    The format is: `<prefix><name>:<__key__>:<0|1>`

- [`BaseMultiplePolicy`][]: Each function has its own key pair, [Redis][] cluster is NOT supported.

    The format is: `<prefix><name>:<__key__>:<function_name>#<function_hash>:<0|1>`

- [`BaseClusterSinglePolicy`][]: All functions share the same key pair, [Redis][] cluster is supported.

    The format is: `<prefix>{<name>:<__key__>}:<0|1>`

- [`BaseClusterMultiplePolicy`][]: Each function has its own key pair, and [Redis][] cluster is supported.

    The format is: `<prefix><name>:<__key__>:<function_name>#{<function_hash>}:<0|1>`

Variables in the format string are defined as follows:

|                 |                                                                   |
| --------------- | ----------------------------------------------------------------- |
| `prefix`        | `prefix` argument of [`RedisFuncCache`][]                         |
| `name`          | `name` argument of [`RedisFuncCache`][]                           |
| `__key__`       | `__key__` attribute the policy class used in [`RedisFuncCache`][] |
| `function_name` | full name of the decorated function                               |
| `function_hash` | hash value of the decorated function                              |

`0` and `1` at the end of the keys are used to distinguish between the two data structures:

- `0`: a sorted or unsorted set, used to store the hash value and sorting score of function invocations
- `1`: a hash table, used to store the return value of the function invocations

If want to use a different format, you can subclass [`AbstractPolicy`][] or any of above policy classes, and implement `calc_keys` method, then pass the custom policy class to [`RedisFuncCache`][].

The following example demonstrates how to custom key format for a _LRU_ policy:

```python
from typing import TYPE_CHECKING, Any, Callable, Mapping, Sequence, Tuple, override

from redis_func_cache import AbstractPolicy, RedisFuncCache
from redis_func_cache.mixins.hash import PickleMd5HashMixin
from redis_func_cache.mixins.policy import LruScriptsMixin

if TYPE_CHECKING:
    from redis.typing import KeyT


def redis_factory():
    ...


MY_PREFIX = "my_prefix"


class MyPolicy(LruScriptsMixin, PickleMd5HashMixin, AbstractPolicy):
    __key__ = "my_key"

    @override
    def calc_keys(
        self, f: Callable|None = None, args: Sequence|None = None, kwds: Mapping[str, Any] | None= None
    ) -> Tuple[KeyT, KeyT]:
        k = f"{self.cache.prefix}-{self.cache.name}-{f.__name__}-{self.__key__}"
        return f"{k}-set", f"{k}-map"

my_cache = RedisFuncCache(name="my_cache", policy=MyPolicy, redis=redis_factory, prefix=MY_PREFIX)

@my_cache
def my_func(...):
    ...
```

In the example, we'll get a cache generates [redis][] keys separated by `-`, instead of `:`, prefixed by `"my-prefix"`, and suffixed by `"set"` and `"map"`, rather than `"0"` and `"1"`. The key pair names could be like `my_prefix-my_cache_func-my_key-set` and `my_prefix-my_cache_func-my_key-map`.

`LruScriptsMixin` tells the policy which lua script to use, and `PickleMd5HashMixin` tells the policy to use [`pickle`][] to serialize and `md5` to calculate the hash value of the function.

### Expirations

## Known Issues

- [`RedisFuncCache`][]'s name

- Can not work with methods of a class which is not serializable.

[redis]: https://redis.io/ "Redis is an in-memory data store used by millions of developers as a cache"

[json]: https://www.json.org/ "JSON (JavaScript Object Notation) is a lightweight data-interchange format."
[`pickle`]: https://docs.python.org/library/pickle.html "The pickle module implements binary protocols for serializing and de-serializing a Python object structure."

[`RedisFuncCache`]: redis_func_cache.types.RedisFuncCache
[`AbstractPolicy`]: redis_func_cache.types.AbstractPolicy

[`BaseSinglePolicy`]: redis_func_cache.policies.base.BaseSinglePolicy
[`BaseMultiplePolicy`]: redis_func_cache.policies.base.BaseMultiplePolicy
[`BaseClusterSinglePolicy`]: redis_func_cache.policies.base.BaseClusterSinglePolicy
[`BaseClusterMultiplePolicy`]: redis_func_cache.policies.base.BaseClusterMultiplePolicy

[`FifoPolicy`]: redis_func_cache.policies.fifo.FifoPolicy "First In First Out policy"
[`LfuPolicy`]: redis_func_cache.policies.lfu.LfuPolicy "Least Frequently Used policy"
[`LruPolicy`]: redis_func_cache.policies.lru.LruPolicy "Least Recently Used policy"
[`MruPolicy`]: redis_func_cache.policies.mru.MruPolicy "Most Recently Used policy"
[`RrPolicy`]: redis_func_cache.policies.rr.RrPolicy "Random Remove policy"
[`TLruPolicy`]: redis_func_cache.policies.tlru.TLruPolicy "Time based Least Recently Used policy."

[`FifoMultiplePolicy`]: redis_func_cache.policies.fifo.FifoMultiplePolicy
[`LfuMultiplePolicy`]: redis_func_cache.policies.lfu.LfuMultiplePolicy
[`LruMultiplePolicy`]: redis_func_cache.policies.lru.LruMultiplePolicy
[`MruMultiplePolicy`]: redis_func_cache.policies.mru.MruMultiplePolicy
[`RrMultiplePolicy`]: redis_func_cache.policies.rr.RrMultiplePolicy
[`TLruMultiplePolicy`]: redis_func_cache.policies.tlru.TLruMultiplePolicy

[`FifoClusterPolicy`]: redis_func_cache.policies.fifo.FifoClusterPolicy
[`LfuClusterPolicy`]: redis_func_cache.policies.lfu.LfuClusterPolicy
[`LruClusterPolicy`]: redis_func_cache.policies.lru.LruClusterPolicy
[`MruClusterPolicy`]: redis_func_cache.policies.mru.MruClusterPolicy
[`RrClusterPolicy`]: redis_func_cache.policies.rr.RrClusterPolicy
[`TLruClusterPolicy`]: redis_func_cache.policies.tlru.TLruClusterPolicy

[`FifoClusterMultiplePolicy`]: redis_func_cache.policies.fifo.FifoClusterMultiplePolicy
[`LfuClusterMultiplePolicy`]: redis_func_cache.policies.lfu.LfuClusterMultiplePolicy
[`LruClusterMultiplePolicy`]: redis_func_cache.policies.lru.LruClusterMultiplePolicy
[`MruClusterMultiplePolicy`]: redis_func_cache.policies.mru.MruClusterMultiplePolicy
[`RrClusterMultiplePolicy`]: redis_func_cache.policies.rr.RrClusterMultiplePolicy
[`TLruClusterMultiplePolicy`]: redis_func_cache.policies.tlru.TLruClusterMultiplePolicy
