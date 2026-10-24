"""deadline 索引的增删与恢复。

deadline 索引是一棵二叉搜索树（``TreeNode.val`` 为请求的 deadline，值互不相同）。新请求到达时要插入，
请求完成后要删除；进程重启时，还要从 checkpoint 里保存的前序遍历序列把索引原样恢复出来。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise
from nanoserve.common.nodes import TreeNode


@exercise("index.insert")
def insert_key(root: TreeNode | None, val: int) -> TreeNode:
    """向 deadline 索引插入一个新请求的 deadline，返回插入后的根节点。

    规格：
      - ``root`` 是一棵二叉搜索树（左子树所有值 < 节点值 < 右子树所有值），可能为空；值互不相同。
      - 保证 ``val`` 不在树中。插入后的树必须仍是二叉搜索树，且恰好包含原有的全部值和 ``val``。
      - 必须复用原树的节点：原树的每个节点对象都要出现在结果中且 ``val`` 不变；只允许新建一个
        值为 ``val`` 的节点。满足条件的树可能不唯一，返回任意一棵即可（最常见的做法是把新节点挂成叶子）。
      - ``root`` 为 None 时返回新建的单节点树。
      - 复杂度 O(h)（h 为树高）。

    示例：
      [4,2,7,1,3]，val=5 -> 例如层序 [4,2,7,1,3,5]
      [40,20,60,10,30,50,70]，val=25 -> 例如层序 [40,20,60,10,30,50,70,None,None,25]
      None，val=5 -> [5]
    """
    raise TODO("index.insert")


@exercise("index.delete")
def delete_key(root: TreeNode | None, key: int) -> TreeNode | None:
    """请求完成后，从 deadline 索引中删除 ``key``，返回删除后的根节点（树变空时返回 None）。

    规格：
      - ``root`` 是二叉搜索树，可能为空；值互不相同。
      - ``key`` 可能不在树中：此时树保持原样不变，返回原来的根。
      - 删除后的树必须仍是二叉搜索树，且恰好包含原有值中除 ``key`` 以外的全部值。
        满足条件的树可能不唯一，返回任意一棵即可；可以就地修改原树的节点（包括改写某个节点的 ``val``）。
      - 复杂度 O(h)（h 为树高）。

    示例：
      [5,3,6,2,4,None,7]，key=3 -> 例如层序 [5,4,6,2,None,None,7]（[5,2,6,None,4,None,7] 也可以）
      [5,3,6,2,4,None,7]，key=0 -> [5,3,6,2,4,None,7]（不存在，原样返回）
      None，key=0 -> None
    """
    raise TODO("index.delete")


@exercise("index.restore")
def bst_from_preorder(preorder: list[int]) -> TreeNode | None:
    """从 checkpoint 中保存的前序遍历序列恢复 deadline 索引。

    规格：
      - ``preorder`` 是某棵二叉搜索树的前序遍历（先根，再左子树，再右子树），值互不相同；
        保证输入合法。值互不相同时这样的二叉搜索树是唯一的，返回它的根节点。
      - 空列表返回 None。保证树高不超过 500。
      - 目标复杂度 O(n)。

    示例：
      [8,5,1,7,10,12] -> 层序 [8,5,10,1,7,None,12]
      [1,3] -> 层序 [1,None,3]
    """
    raise TODO("index.restore")
