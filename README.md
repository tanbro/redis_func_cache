# redis_func_cache

[![python-package](https://github.com/tanbro/redis_func_cache/actions/workflows/python-package.yml/badge.svg)](https://github.com/tanbro/redis_func_cache/actions/workflows/python-package.yml/badge.svg)
[![codecov](https://codecov.io/gh/tanbro/redis_func_cache/graph/badge.svg?token=BgeXJZdPbJ)](https://codecov.io/gh/tanbro/redis_func_cache)
[![readthedocs](https://readthedocs.org/projects/redis-func-cache/badge/)](https://readthedocs.org/projects/redis-func-cache/badge/)

`redis_func_cache` is a _Python_ library for caching function results in [Redis][], similar to the caching functionality provided by the standard library's `functools` module, which comes with some cache decorators, and is quite handy when we want to code something with memorization.
When we need to to cache functions return values distributed over multiple processes or machines, we can use [Redis][] as a backend.

The purpose of the project is to provide a simple and clean way to use [Redis][] as a backend for cache decorators.
It implements `LRU`, `RR`, `FIFO`, `RR` and `LFU` policies([^1]).

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

Using `LRU` cache to decorate a recursive Fibonacci function:

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

In this example, we first create a [Redis][] client, then create a `RedisFuncCache` instance with the [Redis][] client and `LruPolicy` as arguments.
Next, we use the `@lru_cache` decorator to decorate the `fib` function.
This way, each computed result is cached, and subsequent calls with the same parameters retrieve the result directly from the cache, thereby improving performance.

It works almost the same like std-lib's `functools.lru_cache`, except that it uses [Redis][] as a backend, not local machine's memory.

If we browse keys in the [Redis][] database, we can find the cache keys and values.
For the `LruPolicy`, the keys are in a pair form. The pair of keys' names look like:

- `redis_func_cache:my-first-lru-cache:lru:__main__:fib:0`

    The key(`0` suffix) is a sorted set stores functions invoking's hash and corresponding score/weight.

- `redis_func_cache:my-first-lru-cache:lru:__main__:fib:1`

    The key(`1` suffix) is a hash map. Each of it's key is the hash value of a function invoking, and value is the the return value of the function.

### Eviction policies

If you want to use other eviction policies, you can specify the policy class as the second argument of `RedisFuncCache`.

For example, we can use `FifoPolicy` to implement a FIFO cache:

```python
from redis_func_cache import FifoPolicy

fifo_cache = RedisFuncCache("my-cache-2", FifoPolicy, redis_client)

@fifo_cache
def func1(x):
    ...
```

Use `RrPolicy` to implement a random-remove cache:

```python
from redis_func_cache import RrPolicy

rr_cache = RedisFuncCache("my-cache-3", RrPolicy, redis_client)

@rr_cache
def func2(x):
    ...
```

So far, the following policies are available:

- `FifoPolicy`: First In First Out policy
- `LfuPolicy`: Least Frequently Used policy
- `LruPolicy`: Least Recently Used policy
- `MruPolicy`: Most Recently Used policy
- `RrPolicy`: Random Remove policy

- `TLruPolicy`: Time based Least Recently Used policy.

    It is a pseudo LRU policy, not very serious or legitimate.
    The policy removes lowest member based on the timestamp of invocation and does not completely ensure eviction of the least recently used item, since the timestamp may be inaccurate.

    However, the policy is still **MOST RECOMMENDED** for common use. It is faster than the LRU policy and accurate enough for most cases.

> ℹ️ **Info**:\
> Explore source codes in `src/policies` for more details.

### Multiple [Redis][] key pairs

As described above, the cache keys are in a pair form. All decorated functions share the same two keys.
But some times, we may want to use different cache keys for different functions.

One solution is to use different `RedisFuncCache` instances to decorate different functions.
Another way is to use a policy stores cache data in different [Redis][] key pairs for each function.
There are several policies to do that out of the box.

For example, we can use `TLruMultiPolicy` for a LRU cache that has multiple different [Redis][] key pairs to store result values for different functions:

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

In the example, `TLruMultiplePolicy` inherits `BaseMultiplePolicy` which implements how to store cache keys and values for each function.

When called, we can see such keys in the [Redis][] database:

- key pair for `func1`:

  - `redis_func_cache:my-cache-4:tlru-m:__main__:func1#<hash1>:0`
  - `redis_func_cache:my-cache-4:tlru-m:__main__:func1#<hash1>:1`

- key pair for `func2`:

  - `redis_func_cache:my-cache-4:tlru-m:__main__:func2#<hash2>:0`
  - `redis_func_cache:my-cache-4:tlru-m:__main__:func2#<hash2>:1`

where `<hash1>` and `<hash2>` are the hash values of the function definitions.

Policies that store cache in multiple [Redis][] key pairs are:

- `FifoMultiplePolicy`
- `LfuMultiplePolicy`
- `LruMultiplePolicy`
- `MruMultiplePolicy`
- `RrMultiplePolicy`
- `TLruMultiplePolicy`

### Cluster support

The library implements cache algorithms based on a pair of [Redis][] data structures, the two **MUST** be in a same [Redis][] node, or it will not work correctly.

While the [Redis][] cluster will distribute keys to different nodes based on the hash value of the key's name.

To ensure that two keys are placed in the same node, several cluster policies are provided. These policies use the "{...}" part in key names to achieve this.

For example, we can use `TLruClusterPolicy` to implement a cluster-aware LRU cache:

```python
from redis_func_cache import TLruClusterPolicy

cache = RedisFuncCache("my-cluster-cache", TLruClusterPolicy, redis_client)

@cache
def my_func(x):
    ...
```

the key name will be like:

- `redis_func_cache:{my-cluster-cache:tlru-c}:0`
- `redis_func_cache:{my-cluster-cache:tlru-c}:1`

Notice what is in `{...}`: the [Redis][] cluster will determine which node to store the key based on the `{...}` part rather than the entire key name string.

Policies that support cluster are:

- `FifoClusterPolicy`
- `LfuClusterPolicy`
- `LruClusterPolicy`
- `MruClusterPolicy`
- `RrClusterPolicy`
- `TLruClusterPolicy`

### Cluster support with multiple redis key pairs

Policies that support both cluster and store cache in multiple [Redis][] key pairs are:

- `FifoClusterMultiplePolicy`
- `LfuClusterMultiplePolicy`
- `LruClusterMultiplePolicy`
- `MruClusterMultiplePolicy`
- `RrClusterMultiplePolicy`
- `TLruClusterMultiplePolicy`

## Advanced Usage

## Known Issues

- It's default return value serialization is [JSON][], which does not work with complex objects.

    But, still, we can use `pickle` to serialize the return value, by specifying `serializers` argument to `pickle`.

- Can not work with methods of a class which is not serializable.

[^1]: <https://wikipedia.org/wiki/Cache_replacement_policies>

[redis]: https://redis.io/ "Redis is an in-memory data store used by millions of developers as a cache"
[json]: https://www.json.org/ "JSON (JavaScript Object Notation) is a lightweight data-interchange format."
