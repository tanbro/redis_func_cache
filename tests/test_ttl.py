import time
from random import randint
from unittest import TestCase

from ._catches import CACHES


class TTLTest(TestCase):
    def setUp(self):
        """初始化测试环境，清除所有缓存。"""
        super().setUp()
        for cache in CACHES.values():
            cache.policy.purge()

    def test_cache_ttl(self):
        """测试缓存项的独立超时功能。"""
        for cache in CACHES.values():
            # 设置不同的 TTL 值
            ttl_values = [2, 3, 5]  # 不同的超时时间（秒）

            @cache(ttl=ttl_values[0])
            def echo1(x):
                return x

            @cache(ttl=ttl_values[1])
            def echo2(x):
                return x

            @cache(ttl=ttl_values[2])
            def echo3(x):
                return x

            # 调用函数以设置缓存
            val1 = randint(1, 100)
            val2 = randint(1, 100)
            val3 = randint(1, 100)
            echo1(val1)
            echo2(val2)
            echo3(val3)

            # 验证缓存命中
            self.assertEqual(echo1(val1), val1)
            self.assertEqual(echo2(val2), val2)
            self.assertEqual(echo3(val3), val3)

            # 等待超过最小 TTL 时间
            time.sleep(min(ttl_values) + 1)

            # 验证已过期的缓存
            self.assertNotEqual(echo1(val1), val1)
            self.assertEqual(echo2(val2), val2)  # 这个应该还未过期
            self.assertEqual(echo3(val3), val3)  # 这个应该还未过期

            # 等待超过所有 TTL 时间
            time.sleep(max(ttl_values) + 1)

            # 验证所有缓存都已过期
            self.assertNotEqual(echo1(val1), val1)
            self.assertNotEqual(echo2(val2), val2)
            self.assertNotEqual(echo3(val3), val3)
