import asyncio

import pytest
import pytest_asyncio

from ._catches import close_all_async_resources


@pytest.fixture(scope="session")
def event_loop():
    """为异步测试创建一个会话范围的事件循环。"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    try:
        # 确保在关闭事件循环前清理所有异步资源
        pending = asyncio.all_tasks(loop)
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
    except RuntimeError:
        # 如果事件循环已关闭，忽略错误
        pass
    finally:
        if not loop.is_closed():
            loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def cleanup_all_async_resources():
    """在所有测试运行完毕后清理异步资源"""
    yield
    # 尝试获取当前事件循环
    try:
        loop = asyncio.get_event_loop()
        # 如果事件循环未关闭且未运行，则执行清理
        if not loop.is_closed() and not loop.is_running():
            await close_all_async_resources()
    except RuntimeError:
        # 如果没有可用的事件循环，创建一个新的来执行清理
        try:
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            await close_all_async_resources()
            new_loop.close()
        except Exception:
            # 忽略任何清理过程中出现的异常
            pass
    except Exception:
        # 忽略任何其他异常
        pass
