"""轮询式负载均衡的回放分析。

前端把请求按轮询顺序分发给 k 个 worker：第 i 个请求先看 i % k 号 worker，忙就往后找，
找一圈都忙就丢弃请求。回放一段请求日志后，找出承接请求最多的 worker，
用来检查轮询是否真的把负载摊平了。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("sched.rr_busiest")
def busiest_servers(k: int, arrival: list[int], load: list[int]) -> list[int]:
    """轮询负载均衡回放：返回处理请求数最多的 worker（可能有多个）。

    规格：
      - worker 编号 0..k-1，1 <= k；每个 worker 同一时刻最多处理一个请求。
      - 请求 i（下标从 0 开始）在时刻 arrival[i] 到达，处理需要 load[i] 个时间单位：
        若分配给 worker w，则 w 在时间区间 [arrival[i], arrival[i] + load[i])（左闭右开）内忙碌，
        在时刻 arrival[i] + load[i] 重新空闲，可以接同一时刻到达的请求。
      - arrival 非降序（同一时刻可以到达多个请求，按下标顺序依次分配）；0 <= arrival[i]；1 <= load[i]；
        len(arrival) == len(load) >= 1。
      - 分配规则：从 worker (i % k) 开始，按 i % k, i % k + 1, ..., k - 1, 0, 1, ... 的顺序
        （绕一圈）找第一个在时刻 arrival[i] 空闲的 worker；若全部忙碌，丢弃该请求（不计入任何 worker）。
      - 返回成功处理请求数最多的所有 worker 编号，**任意顺序**。
      - 复杂度：O(n log k)。

    示例：
      >>> busiest_servers(3, [1, 2, 3, 4, 5], [5, 2, 3, 3, 3])
      [1]
      >>> sorted(busiest_servers(3, [1, 2, 3, 4], [1, 2, 1, 2]))
      [0]
      >>> sorted(busiest_servers(3, [1, 2, 3], [10, 12, 11]))
      [0, 1, 2]
      >>> sorted(busiest_servers(2, [0, 0, 0, 3], [3, 1, 5, 1]))   # 同一时刻到达：请求 2 时两个 worker 都忙，丢弃
      [1]
    """
    raise TODO("sched.rr_busiest")
