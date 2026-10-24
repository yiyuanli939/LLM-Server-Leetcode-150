"""LoRA adapter 冷却约束下的排程。

多 LoRA 服务中，同一个 adapter 被换入后需要一段冷却时间才能再次加载（例如等待显存回收）。
调度器可以任意安排任务顺序、必要时插入空闲时间片，本文件计算完成所有任务所需的最少时间片数。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("sched.cooldown")
def min_slots_with_cooldown(adapters: list[str], n: int) -> int:
    """同一 LoRA adapter 两次执行之间至少间隔 n 个时间片，求执行完所有任务所需的最少时间片数。

    规格：
      - adapters[i] 是第 i 个任务所需的 adapter 名称（非空字符串，相同名称表示同一 adapter）；
        1 <= len(adapters)。0 <= n。
      - 每个时间片要么执行恰好一个任务（耗时 1 个时间片），要么空闲。任务顺序可任意安排。
      - 约束：使用同一 adapter 的任意两个任务，执行时间片之间至少隔 n 个时间片
        （即若分别在第 a、b 片执行且 a < b，则 b - a > n）。
      - 返回执行完所有任务所需的最少时间片数（包括中间插入的空闲片）。
      - 复杂度：O(len(adapters))。

    示例：
      >>> min_slots_with_cooldown(["A", "A", "A", "B", "B", "B"], 2)
      8
      >>> min_slots_with_cooldown(["A", "C", "A", "B", "D", "B"], 1)
      6
      >>> min_slots_with_cooldown(["A", "A", "A", "B", "B", "B"], 3)
      10
    """
    raise TODO("sched.cooldown")
