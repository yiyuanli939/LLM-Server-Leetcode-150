"""带 TTL 的 API token / 会话管理。

服务器给每个会话签发一个 token，token 在签发（或最近一次续期）后 ttl 个时间单位过期。
活跃的会话可以续期；准入控制需要随时知道当前还有多少个未过期的 token。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("server.tokens")
class TokenManager:
    """API token 管理：带 TTL 的签发、续期、统计有效 token。

    规格：
      - ``TokenManager(ttl)``：每个 token 的有效期为 ttl（``ttl >= 1``）。
      - ``generate(token_id, now)``：在时刻 now 签发一个新 token，过期时刻为 ``now + ttl``。
        保证 token_id 之前从未被签发过。
      - ``renew(token_id, now)``：若 token_id 存在且在时刻 now **未过期**，把它的过期时刻改为
        ``now + ttl``；若 token 不存在或已过期，则忽略本次调用（什么也不做）。
      - ``count_unexpired(now)``：返回时刻 now 未过期的 token 个数。
      - 过期判定：过期时刻为 t 的 token 在时刻 t **已经过期**——过期先于同一时刻的其它操作发生，
        因此在时刻 t 既不能续期它，也不计入 count_unexpired(t)。
      - 所有调用的 now **非降序**（同一时刻可以有多次调用，例如同一 tick 里到达的多个请求）；
        token_id 为非空字符串；generate / renew 返回 None。

    示例：
      >>> m = TokenManager(5)
      >>> m.renew("aaa", 1)               # 不存在，忽略
      >>> m.generate("aaa", 2)            # 过期时刻 7
      >>> m.count_unexpired(6)
      1
      >>> m.generate("bbb", 7)            # 过期时刻 12；"aaa" 在 7 已过期
      >>> m.renew("aaa", 8)               # 已过期，忽略
      >>> m.renew("bbb", 10)              # 过期时刻改为 15
      >>> m.count_unexpired(15)
      0
      >>> m2 = TokenManager(4)
      >>> m2.generate("x", 3); m2.generate("y", 3)   # 同一时刻签发两个
      >>> m2.count_unexpired(3)
      2
      >>> m2.renew("x", 6); m2.count_unexpired(7)     # "x" 续到 10，"y" 在 7 已过期
      1
    """

    def __init__(self, ttl: int) -> None:
        raise TODO("server.tokens")

    def generate(self, token_id: str, now: int) -> None:
        raise TODO("server.tokens")

    def renew(self, token_id: str, now: int) -> None:
        raise TODO("server.tokens")

    def count_unexpired(self, now: int) -> int:
        raise TODO("server.tokens")
