# redcache

redcache it a python library to implement distributed cache using [redis][].

Python standard library `functools` comes with some cache decorators. It is quite handy when we want to code something with memorization.

When we need to to cache a function return value distributed over multiple processes or machines, we can use [redis][] as a backend.

The purpose of the project is to provide a simple and clean way to use [redis][] as a backend for cache decorators.

> ❗ **Note**:\
> The project is still under development, and **DO NOT USE IT IN PRODUCTION**

## Install

- install from PyPI:

    ```bash
    pip install -U redcache
    ```

- install from source:

    1. clone it:

        ```bash
        git clone https://github.com/tanbro/redcache.git
        ```

    1. install:

        ```bash
        cd redcache
        python setup.py install
        ```

## Basic Usage

### First example

Using `LRU` cache to decorate a recursive Fibonacci function:

```python
from redis import Redis
from redcache import RedCache, LruPolicy

redis_client = Redis(...)

lru_cache = RedCache("my-cache", redis_client, LruPolicy)

@lru_cache
def fib(n):
    if n <= 1:
        return n
    if n == 2:
        return 1
    return fib(n - 1) + fib(n - 2)
```

In this example, we first create a [Redis][] client, then create a `RedCache` instance with the [redis][] client and `LruPolicy` as arguments.
Next, we use the `@lru_cache` decorator to decorate the `fib` function.
This way, each computed result is cached, and subsequent calls with the same parameters retrieve the result directly from the cache, thereby improving performance.

It works almost the same like std-lib's `functools.lru_cache`, except that it uses [redis][] as a backend, not local machine's memory.

If we browse keys in the [Redis] database, we can find the cache keys and values.
For the `LruPolicy`, the keys are in a pair form. The pair of keys' names look like:

- `redcache:my-cache:lru:__main__:fib:0`

    The key (`0` suffix) is a set stores functions invoking's hash and corresponding score/weight.

- `redcache:my-cache:lru:__main__:fib:1`

    The key(`1` suffix) is a hash map , it's key is hash value of the function invoking, and value is the actual cached return value.

### Eviction policies

If you want to use other eviction policies, you can specify the policy class as the second argument of `RedCache`.

For example, we can use `FifoPolicy` to implement a FIFO cache:

```python
from redcache import FifoPolicy

fifo_cache = RedCache("my-cache", redis_client, FifoPolicy)

@fifo_cache
def func1(x):
    ...
```

Use `RrPolicy` to implement a random-remove cache:

```python
from redcache import RrPolicy

rr_cache = RedCache("my-cache", redis_client, rr_cache)

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

    However, the policy is still recommended for common use. It is faster than the LRU policy and accurate enough for most cases.

> ℹ️ **Info**:\
> Explore source codes in `src/policies` for more details.

### Multiple [redis][] key pairs

As described above, the cache keys are in a pair form. All decorated functions share the same two keys.
But some times, we may want to use different cache keys for different functions.

One solution is to use different `RedCache` instances to decorate different functions.
Another way is to use a policy support store cache data in different [redis][] key pairs for each function.
There are several policies to do that out of the box.

For example, we can use `LruMultiPolicy` to implement a LRU cache stored in multiple [redis][] key pairs:

```python
from redcache import TLruMultiplePolicy

cache = RedCache("my-cache", redis_client, TLruMultiplePolicy)

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

  - `redcache:my-cache:tlru-m:__main__:func1#<hash1>:0`
  - `redcache:my-cache:tlru-m:__main__:func1#<hash1>:1`

- key pair for `func2`:

  - `redcache:my-cache:tlru-m:__main__:func2#<hash2>:0`
  - `redcache:my-cache:tlru-m:__main__:func2#<hash2>:1`

where `<hash1>` and `<hash2>` are the hash values of the function definitions.

Policies that store cache in multiple [redis][] key pairs are:

- `FifoMultiplePolicy`
- `LfuMultiplePolicy`
- `LruMultiplePolicy`
- `MruMultiplePolicy`
- `RrMultiplePolicy`
- `TLruMultiplePolicy`

### Cluster support

The library implements cache algorithms based on a pair of [redis][] data structures, the two **MUST** be in a same [redis][] node, or it will not work correctly.

While the [redis][] cluster will distribute keys to different nodes based on the hash value of the key's name.

To ensure that two keys are placed in the same node, several cluster policies are provided. These policies use the "{...}" part in key names to achieve this.

For example, we can use `TLruClusterPolicy` to implement a cluster-aware LRU cache:

```python
from redcache import TLruClusterPolicy

cache = RedCache("my-cluster-cache", redis_client, TLruClusterPolicy)

@cache
def my_func(x):
    ...
```

the key name will be like:

- `redcache:{my-cluster-cache:tlru-c}:0`
- `redcache:{my-cluster-cache:tlru-c}:1`

Notice what is in `{...}`: the [redis][] cluster will determine which node to store the key based on the `{...}` part rather than the entire key name string.

Policies that support cluster are:

- `FifoClusterPolicy`
- `LfuClusterPolicy`
- `LruClusterPolicy`
- `MruClusterPolicy`
- `RrClusterPolicy`
- `TLruClusterPolicy`

### Cluster support with multiple redis key pairs

Policies that support both cluster and store cache in multiple [redis][] key pairs are:

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

[redis]: https://redis.io/ "Redis is an in-memory data store used by millions of developers as a cache"
[json]: https://www.json.org/ "JSON (JavaScript Object Notation) is a lightweight data-interchange format."

<https://medium.com/@thebestchef/using-redis-in-python-lru-cache-56594df3582c>

<https://redis.io/glossary/lru-cache/>

<https://wikipedia.org/wiki/Cache_replacement_policies>
