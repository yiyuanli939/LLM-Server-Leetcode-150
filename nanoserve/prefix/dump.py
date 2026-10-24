"""按层 dump deadline 索引树的结构。

调试 EDF 等待队列时需要把 deadline 索引（一棵二叉搜索树）按层打印出来，一眼看出它是否失衡。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise
from nanoserve.common.nodes import TreeNode


@exercise("prefix.level_dump")
def level_dump(root: TreeNode | None) -> list[list[int]]:
    """按层 dump deadline 索引树。

    规格：
      - 返回列表的第 i 项是第 i 层（根为第 0 层）所有节点的值，层内**从左到右**。
      - 空树返回 ``[]``。

    示例：
      树 [3,9,20,None,None,15,7] -> [[3],[9,20],[15,7]]
      树 [1] -> [[1]]
    """
    raise TODO("prefix.level_dump")


