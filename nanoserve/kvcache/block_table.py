"""块表（block table）上的链式操作。

每个序列的 KV Cache 由若干物理块串成一条链。本文件实现对块链的结构性操作：
并行采样时 fork 整条链、检测链是否损坏成环、按滑动窗口丢块、局部反转、旋转与按热度分区。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise
from nanoserve.common.nodes import ListNode, RandomListNode


@exercise("kv.fork")
def fork_chain(head: RandomListNode | None) -> RandomListNode | None:
    """并行采样（n > 1）时把一条块链 fork 出一份独立副本。每个块除了 ``next`` 之外，
    还有一个 ``random`` 指针，指向同一条链中的任意块（共享引用），或为 ``None``。

    规格：
      - 返回新链的头结点；新链必须由全新的结点组成（深拷贝），不得复用原链的任何结点。
      - 新链中每个结点的 ``val`` 与原链对应位置相同；新链的 ``next`` / ``random`` 指针
        只能指向新链中的结点，且指向的位置与原链一一对应（``random`` 为 ``None`` 则保持 ``None``）。
      - 原链在函数返回后必须保持原样（结构与值都不变）。
      - ``head`` 为 ``None`` 时返回 ``None``。链长 0 ~ 10^4。

    示例（用 ``[val, random 指向的下标]`` 描述每个块，下标从 0 开始）：
      原链 [[7,None],[13,0],[11,4],[10,2],[1,0]]
      → 副本同样是 [[7,None],[13,0],[11,4],[10,2],[1,0]]，但所有结点都是新的。
      原链 [[4,None],[9,0],[2,1]]（每个块的 random 指向前一个块）→ 副本 [[4,None],[9,0],[2,1]]
    """
    raise TODO("kv.fork")


@exercise("kv.has_cycle")
def has_cycle(head: ListNode | None) -> bool:
    """块链损坏检测：链表正常时以 ``None`` 结尾；若某个块的 ``next`` 指回了链中更早的块，
    遍历将永不结束——这说明块表已损坏。

    规格：
      - 若沿 ``next`` 走下去会重新回到某个已经过的结点，返回 ``True``；否则返回 ``False``。
      - 不得修改链表。额外空间须为 O(1)（不要用 set 记录访问过的结点）。
      - 链长 0 ~ 10^4；``head`` 为 ``None`` 时返回 ``False``。

    示例：
      3 -> 2 -> 0 -> -4 -> (回到 2)   → True
      1 -> 2 -> (回到 1)              → True
      1                               → False
    """
    raise TODO("kv.has_cycle")


@exercise("kv.partition_hot")
def partition_by_heat(head: ListNode | None, x: int) -> ListNode | None:
    """按热度分区：链中每个结点的 ``val`` 是该块的热度值。把热度 ``< x`` 的块排到前面，
    热度 ``>= x`` 的块排到后面。

    规格：
      - 两部分内部都必须保持原有的相对顺序（稳定分区）。返回新的链头。
      - 链长 0 ~ 200；``val`` 与 ``x`` 都在 [-200, 200] 内（可能为负）。

    示例：
      1->4->3->2->5->2, x=3  → 1->2->2->4->3->5
      2->1, x=2              → 1->2
    """
    raise TODO("kv.partition_hot")
