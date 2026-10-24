"""前缀缓存树的持久化。

重启引擎时希望保留热前缀：把缓存树编码成一个字符串写盘，下次启动再原样还原。
编码格式由你自定，唯一要求是无损往返。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise
from nanoserve.common.nodes import TreeNode


@exercise("prefix.codec")
class TreeCodec:
    """二叉树 <-> 字符串 的编解码器，格式任意，只要求 ``deserialize(serialize(t))`` 与 t 结构和值完全相同。

    规格：
      - ``serialize(root)``：把以 ``root`` 为根的二叉树（可为 None）编码成一个 ``str``。
      - ``deserialize(data)``：把 ``serialize`` 产生的字符串还原成树，返回根（空树返回 None）。
      - 节点值为整数，可为负、可重复；节点数最多约 10^4。
      - 树可能极度不平衡（例如深度达到上千的单链），实现不能因此崩溃（注意 Python 递归深度限制）。
      - 编解码器应是无状态的：不得借助类/全局变量在两次调用之间传递信息。
      - 只有 ``val/left/right`` 需要还原，``next`` 字段忽略。

    示例：
      >>> c = TreeCodec()
      >>> tree_to_level(c.deserialize(c.serialize(tree_from_level([1, 2, 3, None, None, 4, 5]))))
      [1, 2, 3, None, None, 4, 5]
    """

    def serialize(self, root: TreeNode | None) -> str:
        raise TODO("prefix.codec")

    def deserialize(self, data: str) -> TreeNode | None:
        raise TODO("prefix.codec")
