"""测试专用的极简替身：调用记录器 + patch 上下文管理器，纯 pytest 实现。"""

from collections.abc import Callable
from contextlib import contextmanager
from inspect import isawaitable, iscoroutinefunction
from typing import Any


class CallRecorder:
    """记录调用的可调用对象，可返回固定值或转发给 side_effect。"""

    def __init__(self, return_value: Any = None, side_effect: Callable | None = None):
        self.return_value = return_value
        self.side_effect = side_effect
        self.calls: list[tuple[tuple, dict]] = []
        self.call_args: tuple[tuple, dict] = ((), {})

    def __call__(self, *args, **kwargs):
        self._record(args, kwargs)
        if self.side_effect is not None:
            return self.side_effect(*args, **kwargs)
        return self.return_value

    def _record(self, args, kwargs):
        self.calls.append((args, kwargs))
        self.call_args = (args, kwargs)

    def assert_called_once(self):
        assert len(self.calls) == 1, f"expected 1 call, got {len(self.calls)}"

    def assert_not_called(self):
        assert not self.calls, f"expected no calls, got {len(self.calls)}"


class AsyncCallRecorder(CallRecorder):
    """异步版本：side_effect 可以是异步可调用对象。"""

    async def __call__(self, *args, **kwargs):
        self._record(args, kwargs)
        if self.side_effect is not None:
            result = self.side_effect(*args, **kwargs)
            if isawaitable(result):
                result = await result
            return result
        return self.return_value


@contextmanager
def patch_object(obj: Any, name: str, return_value: Any = None, side_effect: Callable | None = None):
    """在上下文内把 ``obj.name`` 替换为记录器，退出时恢复原值。

    根据被替换目标的原属性是否为协程函数自动选择同步/异步记录器。
    """
    recorder: CallRecorder
    if iscoroutinefunction(getattr(obj, name)):
        recorder = AsyncCallRecorder(return_value=return_value, side_effect=side_effect)
    else:
        recorder = CallRecorder(return_value=return_value, side_effect=side_effect)
    original = getattr(obj, name)
    setattr(obj, name, recorder)
    try:
        yield recorder
    finally:
        setattr(obj, name, original)
