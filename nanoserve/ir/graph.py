"""计算图（IR）的结构性分析。

模型被编译成算子依赖图之后，引擎需要先确认图是否无环、能否排出一个合法执行顺序，
并且在做图优化 pass 之前对整张图做一次深拷贝，避免改坏原图。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise
from nanoserve.common.nodes import GraphNode


@exercise("ir.order_ok")
def can_schedule(n: int, deps: list[list[int]]) -> bool:
    """判断由 n 个算子组成的依赖图是否存在合法的执行顺序（即依赖关系无环）。

    规格：
      - 算子编号 0..n-1（``n >= 1``）。
      - ``deps[i] = [a, b]`` 表示算子 a 依赖算子 b：b 必须先于 a 执行。
      - 若存在一个顺序能执行完全部 n 个算子（依赖图无环）返回 True，否则返回 False。
      - deps 可为空；保证没有重复的 [a, b] 对。复杂度 O(n + len(deps))。

    示例：
      >>> can_schedule(2, [[1, 0]])
      True
      >>> can_schedule(2, [[1, 0], [0, 1]])
      False
    """
    raise TODO("ir.order_ok")


@exercise("ir.order")
def topo_order(n: int, deps: list[list[int]]) -> list[int]:
    """给出 n 个算子的任意一个合法执行顺序；若依赖有环则返回空列表。

    规格：
      - 算子编号 0..n-1（``n >= 1``）；``deps[i] = [a, b]`` 表示 a 依赖 b（b 先执行）。
      - 返回值是 0..n-1 的一个排列，且对每个 [a, b]，b 在 a 之前出现。
      - 合法顺序可能不唯一，返回任意一个即可；有环时返回 ``[]``。
      - 复杂度 O(n + len(deps))。

    示例：
      >>> topo_order(2, [[1, 0]])
      [0, 1]
      >>> topo_order(4, [[1, 0], [2, 0], [3, 1], [3, 2]])  # [0, 2, 1, 3] 也合法
      [0, 1, 2, 3]
    """
    raise TODO("ir.order")


@exercise("ir.clone")
def clone_graph(node: GraphNode | None) -> GraphNode | None:
    """在图优化 pass 之前，对一张无向连通的算子图做深拷贝。

    规格：
      - 输入是图中某个节点（值为 1 的节点）的引用；图无向且连通，每个节点 ``val`` 唯一
        （1..n），``neighbors`` 列出其相邻节点。无自环、无重边。
      - 返回新图中与输入节点对应的节点：新图的结构（每个节点的 val 及邻居 val 的顺序）
        与原图完全一致，但所有节点都是新创建的对象，不得与原图共享任何节点。
      - 不得修改原图。输入为 None（空图）时返回 None。

    示例：
      邻接表（第 i 项是值为 i+1 的节点的邻居）[[2, 4], [1, 3], [2, 4], [1, 3]] 的图，
      拷贝后得到邻接表相同、但节点对象全新的图。
    """
    raise TODO("ir.clone")
