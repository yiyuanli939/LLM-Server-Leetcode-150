"""算子依赖的可达性分析。

图优化 pass 需要回答两类问题：两个算子之间是否存在（传递的）先后约束——没有约束的算子才能并行；
以及在只提供了一部分输入张量时，哪些算子的输出最终能被计算出来。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("ir.depends_on")
def depends_queries(n: int, deps: list[list[int]], queries: list[list[int]]) -> list[bool]:
    """批量回答"算子 u 是否必须先于算子 v 执行"，用于判断两个算子能否并行。

    规格：
      - 算子编号 0..n-1（``n >= 1``）。``deps[i] = [a, b]`` 表示 a 必须先于 b 执行（注意方向）。
        保证依赖图无环、没有重复的 [a, b] 对，且 a != b。deps 可以为空。
      - 先后约束可以传递：若 a 先于 b、b 先于 c，则 a 也必须先于 c。
      - ``queries[j] = [u, v]``（保证 u != v）：u 是否（直接或传递地）必须先于 v 执行。
        返回与 queries 等长、按下标一一对应的布尔列表。
      - 规模：n <= 100，len(queries) <= 10^4。

    示例：
      >>> depends_queries(2, [[1, 0]], [[0, 1], [1, 0]])
      [False, True]
      >>> depends_queries(2, [], [[1, 0], [0, 1]])
      [False, False]
      >>> depends_queries(3, [[1, 2], [1, 0], [2, 0]], [[1, 0], [1, 2]])
      [True, True]
    """
    raise TODO("ir.depends_on")


@exercise("ir.computable")
def computable_outputs(outputs: list[str], inputs: list[list[str]], provided: list[str]) -> list[str]:
    """给定一开始就提供的张量，找出所有能被计算出来的算子输出。

    规格：
      - ``outputs[i]`` 是第 i 个算子产出的张量名，计算它需要 ``inputs[i]`` 中的**全部**张量
        （``inputs[i]`` 至少一个元素，元素互不重复）；``len(outputs) == len(inputs)``。
      - ``provided`` 是一开始就有的张量，可以被任意多个算子使用。outputs 与 provided 中的名字
        合在一起互不重复。
      - 一个算子的输出也可以作为别的算子的输入，只要先把它算出来。``inputs`` 中也可能出现既不在
        provided、也不是任何算子输出的名字——依赖它的算子永远算不出来。
      - 输出能被计算出来，当且仅当存在一个有限的计算顺序，使得每一步用到的张量都已提供或已算出。
        因此处在依赖环上（或依赖于环上输出）的算子都算不出来。
      - 返回所有能计算出来的输出名，**顺序任意**，不重复。
      - 复杂度：O(len(outputs) + 所有 inputs[i] 的长度之和)（把字符串哈希视为 O(1)）。

    示例：
      outputs=["attn"], inputs=[["q", "k"]], provided=["q", "k", "v"] -> ["attn"]
      outputs=["attn", "proj"], inputs=[["q", "k"], ["attn", "w_o"]], provided=["q", "k", "w_o"]
        -> ["attn", "proj"]
    """
    raise TODO("ir.computable")
