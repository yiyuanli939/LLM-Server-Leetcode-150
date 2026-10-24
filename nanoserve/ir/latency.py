"""计算图与设备拓扑上的时间分析。

编译 IR 之后需要估算两类时间：一是从某个设备把数据广播到所有设备需要多久（最短路），
二是在无限并行的前提下跑完整张算子依赖图需要多久（关键路径）。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("ir.op_latency")
def broadcast_latency(edges: list[list[int]], n: int, src: int) -> int:
    """设备 1..n 之间有有向带权链路，求从 src 广播到所有设备的最短完成时间。

    规格：
      - ``edges[i] = [u, v, w]``：从设备 u 到设备 v 的有向链路，传输耗时 w（``w >= 0``）。
        设备编号 1..n；保证没有重复的 (u, v) 对、没有自环。
      - 数据从 ``src`` 在时刻 0 出发，沿链路传播；每台设备收到的时刻是从 src 到它的最短路长度。
      - 返回所有 n 台设备都收到数据的时刻（即最短路长度的最大值）；若有设备不可达，返回 -1。
      - n = 1 时返回 0。复杂度应为 O(E log V) 级别。

    示例：
      >>> broadcast_latency([[2, 1, 1], [2, 3, 1], [3, 4, 1]], 4, 2)
      2
      >>> broadcast_latency([[1, 2, 1]], 2, 2)
      -1
    """
    raise TODO("ir.op_latency")


@exercise("ir.critical_path")
def critical_path_time(n: int, deps: list[list[int]], cost: list[int]) -> int:
    """算子 1..n 组成有向无环依赖图，在并行度不受限的前提下，求跑完全部算子的最短时间。

    规格：
      - ``deps[j] = [a, b]``：算子 a 必须完成之后算子 b 才能开始（b 依赖 a）；算子编号 1..n。
      - ``cost[i]`` 是算子 i+1 的执行耗时（注意 0 起下标对应 1 起编号），均为正整数。
      - 任意多个依赖已满足的算子可同时执行；返回所有算子都完成的最早时刻（关键路径长度）。
      - 保证依赖图无环；deps 可为空。复杂度 O(n + len(deps))。

    示例：
      >>> critical_path_time(3, [[1, 3], [2, 3]], [3, 2, 5])
      8
      >>> critical_path_time(5, [[1, 5], [2, 5], [3, 5], [3, 4], [4, 5]], [1, 2, 3, 4, 5])
      12
    """
    raise TODO("ir.critical_path")
