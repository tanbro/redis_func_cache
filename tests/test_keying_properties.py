"""multiple / cluster keying 的纯计算特性测试（不需要 Redis 服务器）。

- multiple：每个函数独立键对，键名由函数全名 + 字节码校验和构成——
  同名不同实现的函数必须得到不同键，同一函数重复计算必须确定。
- cluster：hash tag 保证键对内两键落在同一 slot（多键命令/Lua 才不会报
  CROSSSLOT）；tag 放置正确（slot 只由花括号内片段决定，:0/:1 后缀在括号外）。
"""

from redis.crc import key_slot

from redis_func_cache.keying import ClusterMultipleKeying, ClusterSingleKeying, MultipleKeying


def _slots(*keys: str) -> set[int]:
    return {key_slot(key.encode()) for key in keys}


def test_cluster_single_pair_co_located():
    """单键对变体：tag 包住 name:key，:0/:1 后缀不改变 slot。"""
    keying = ClusterSingleKeying("lru")
    index_key, value_key = keying.calc_key_pair("p", "name")
    assert index_key == "p{name:lru}:0"
    assert value_key == "p{name:lru}:1"
    # 两键同 slot：否则集群上 Lua / 多键命令报 CROSSSLOT
    assert len(_slots(index_key, value_key)) == 1
    # slot 只由花括号内片段决定（与不带后缀的基础键一致）
    assert key_slot(b"p{name:lru}") in _slots(index_key, value_key)


def test_cluster_multiple_pair_co_located_per_function():
    """多键对变体：tag 包住校验和，每个函数的键对内部同 slot。"""
    keying = ClusterMultipleKeying("lru")

    def fn_a(x):
        return x

    def fn_b(x):
        return x + 1

    pair_a = keying.calc_key_pair("p", "name", fn_a)
    pair_b = keying.calc_key_pair("p", "name", fn_b)

    # 键对内共置：a 的两键同 slot，b 的两键同 slot
    assert len(_slots(*pair_a)) == 1
    assert len(_slots(*pair_b)) == 1

    # 不同函数 → 不同键对（不同校验和 tag），键名与 slot 均不冲突
    assert pair_a != pair_b


def test_multiple_same_name_different_bytecode():
    """同名函数、不同实现（字节码不同）必须得到不同键对。"""
    keying = MultipleKeying("lru")

    def make_echo(body):
        if body == 0:

            def echo(x):
                return x

        else:

            def echo(x):
                return x + 1

        return echo

    echo_plain = make_echo(0)
    echo_increment = make_echo(1)

    pair_plain = keying.calc_key_pair("p", "name", echo_plain)
    pair_increment = keying.calc_key_pair("p", "name", echo_increment)
    assert pair_plain != pair_increment


def test_multiple_deterministic_and_identity():
    """同一函数重复计算键对确定；全名与字节码都相同的函数共享键对。"""
    keying = MultipleKeying("lru")

    def make():
        def fn(x):
            return x

        return fn

    f1 = make()
    f2 = make()

    # 同一函数（全名 + 字节码相同）→ 同一键对：这是键身份模型的边界语义
    pair_1 = keying.calc_key_pair("p", "name", f1)
    assert keying.calc_key_pair("p", "name", f1) == pair_1  # 确定
    assert keying.calc_key_pair("p", "name", f2) == pair_1

    # 名字不同 → 键对不同
    def other(x):
        return x

    assert keying.calc_key_pair("p", "name", other) != pair_1
