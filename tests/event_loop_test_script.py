#!/usr/bin/env python3
"""
简单的测试脚本，用于验证事件循环关闭问题是否已修复。
此脚本可以独立运行，用于快速验证修复效果。
"""

import asyncio
import sys
from uuid import uuid4

from ._catches import ASYNC_CACHES


async def test_single_cache(cache_name, cache):
    """测试单个缓存实例"""
    print(f"Testing cache: {cache_name}")

    @cache
    async def echo(x):
        await asyncio.sleep(0)
        return x

    val = uuid4().hex
    result = await echo(val)
    assert result == val, f"Expected {val}, got {result}"
    print(f"  Test passed for {cache_name}")


async def main():
    """主测试函数"""
    print("Starting event loop close error test...")

    # 清理之前的缓存
    coros = (cache.policy.apurge() for cache in ASYNC_CACHES.values())
    await asyncio.gather(*coros)

    # 测试所有缓存
    for cache_name, cache in ASYNC_CACHES.items():
        await test_single_cache(cache_name, cache)

    print("All tests passed!")

    # 手动清理资源
    tasks = []
    for cache in ASYNC_CACHES.values():
        if hasattr(cache.client, "aclose"):
            tasks.append(cache.client.aclose())
        elif hasattr(cache.client, "close"):
            tasks.append(cache.client.close())

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

    print("Resources cleaned up successfully!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
        print("Test completed successfully without event loop errors!")
        sys.exit(0)
    except Exception as e:
        print(f"Test failed with error: {e}")
        sys.exit(1)
