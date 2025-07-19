from random import randint
from unittest import TestCase
from unittest.mock import patch

from ._catches import CACHES


class ContextTest(TestCase):
    def setUp(self):
        """初始化测试环境，清除所有缓存。"""
        super().setUp()
        for cache in CACHES.values():
            cache.policy.purge()

    def test_cache_disabled(self):
        """测试在 disable_cache 上下文中缓存是否被禁用。"""
        for cache in CACHES.values():

            @cache.decorate()
            def echo(x):
                return x

            val = randint(1, 100)
            # 正常调用，缓存应生效
            self.assertEqual(echo(val), val)
            with patch.object(cache, "put") as mock_put:
                self.assertEqual(echo(val), val)
                mock_put.assert_not_called()

            # 在 disable_cache 上下文中调用，缓存应失效
            with cache.disable():
                # 直接调用函数，不经过缓存
                with patch.object(cache, "get") as mock_get:
                    with patch.object(cache, "put") as mock_put:
                        # 模拟缓存未命中时的返回值
                        mock_get.return_value = None
                        result = echo(val)  # 不触发缓存写入
                        # 确保 get 未被调用
                        mock_get.assert_not_called()
                        # 确保 put 未被调用
                        mock_put.assert_not_called()
                        # 确保返回值正确
                        self.assertEqual(result, val)

            # 离开上下文后，缓存应恢复正常
            with patch.object(cache, "get", return_value=cache.serialize(val)) as mock_get:
                with patch.object(cache, "put") as mock_put:
                    result = echo(val)
                    mock_get.assert_called_once()
                    mock_put.assert_not_called()
                    self.assertEqual(result, val)
