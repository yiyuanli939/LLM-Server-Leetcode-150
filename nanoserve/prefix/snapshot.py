"""deadline 索引快照的比较。

等待队列的 deadline 索引会定期写成 checkpoint，重启时据此重建；写完 checkpoint 要立即读回，
与内存中的索引逐节点比较，确认两份快照完全一致。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise
from nanoserve.common.nodes import TreeNode


@exercise("prefix.same_snapshot")
def same_tree(a: TreeNode | None, b: TreeNode | None) -> bool:
    """两份 deadline 索引快照是否完全一致。

    规格：
      - 当且仅当两棵树结构完全相同（每个位置要么都有节点、要么都为空）且对应节点值相等时返回 True。
      - 两棵都为空树时返回 True。

    示例：
      [1,2,3] vs [1,2,3] -> True
      [1,2] vs [1,None,2] -> False
      [1,2,1] vs [1,1,2] -> False
    """
    raise TODO("prefix.same_snapshot")


