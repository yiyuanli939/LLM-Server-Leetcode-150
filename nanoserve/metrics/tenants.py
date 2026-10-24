"""租户维度的请求统计。

Metrics 模块按租户 id 统计请求分布，用来发现"单一租户占据过半流量"这种需要限流的情形。
流量日志可能很长，统计时要求只用常数额外空间。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("metrics.dominant")
def dominant_tenant(requests: list[int] | list[str]) -> int | str:
    """找出占请求总数一半以上的租户。

    规格：
      - requests 非空，requests[i] 是第 i 个请求所属的租户 id：整数（可为负）或字符串
        （例如 "acme"）；只用 == 比较 id，同一个列表里的 id 类型相同。
      - 若存在某个租户 id 出现次数严格大于 len(requests) // 2，必须返回该 id。
      - 若不存在这样的租户，可以返回 requests 中出现过的**任意一个** id（调用方会再数一遍确认），
        但不能抛异常、不能返回列表里没有的值。
      - 复杂度：O(n) 时间，O(1) 额外空间。

    示例：
      >>> dominant_tenant([3, 2, 3])
      3
      >>> dominant_tenant([2, 2, 1, 1, 1, 2, 2])
      2
      >>> dominant_tenant(["acme", "beta", "acme"])
      'acme'
      >>> dominant_tenant(["a", "b", "c"]) in ("a", "b", "c")   # 没有过半租户：返回任意一个出现过的 id
      True
    """
    raise TODO("metrics.dominant")
