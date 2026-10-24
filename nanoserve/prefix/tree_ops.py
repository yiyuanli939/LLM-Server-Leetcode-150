"""二叉树的基础结构查询，服务于 deadline 索引。

EDF 等待队列把带 deadline 的请求放在一棵二叉搜索树里（``TreeNode``，``val`` 为请求的排序键）。
这里提供两个最常用的结构查询：两个节点在树上从哪里分叉（区间查询的起点），以及树有多深（判断是否失衡、需要重建）。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise
from nanoserve.common.nodes import TreeNode


@exercise("prefix.fork_point")
def fork_point(root: TreeNode, p: TreeNode, q: TreeNode) -> TreeNode:
    """deadline 区间查询的分叉点：区间两端各落在索引树的某个节点上，找出两条根路径开始分叉的那个节点，
    整个区间都在它的子树里。这个查询只看节点在树中的位置、不比较节点值，所以对任意二叉树都成立。

    规格：
      - ``root`` 为一棵普通二叉树（**不是** BST，节点值无序），节点值互不相同。
      - ``p``、``q`` 是这棵树中的两个不同节点（就是树里的节点对象本身，不是值），保证都存在。
      - 返回同时以 p 和 q 为后代的、深度最大的节点（节点也算作它自己的后代）。
        也就是说如果 p 是 q 的祖先，答案就是 p。
      - 返回的必须是树中的节点对象本身。

    示例（层序表示，None 表示空位）：
      树 [3,5,1,6,2,0,8,None,None,7,4]，p=5，q=1 -> 节点 3
      同一棵树，p=5，q=4 -> 节点 5
    """
    raise TODO("prefix.fork_point")


@exercise("prefix.depth")
def max_depth(root: TreeNode | None) -> int:
    """deadline 索引树的最大深度：从根到最远叶子的路径上的**节点数**。深度过大说明索引失衡，需要重建。

    规格：
      - 空树返回 0；只有根节点返回 1。

    示例：
      树 [3,9,20,None,None,15,7] -> 3
      树 [1,None,2] -> 2
    """
    raise TODO("prefix.depth")
