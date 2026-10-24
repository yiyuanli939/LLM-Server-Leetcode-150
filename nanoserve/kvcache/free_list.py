"""空闲块链表（free list）。

块管理器把回收的物理块号挂在按块号升序排列的空闲链表上，以便优先分配低地址块、
减少碎片。本文件实现空闲链表的合并、排序整理与重复释放隔离。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise
from nanoserve.common.nodes import ListNode


@exercise("kv.merge_free")
def merge_free_lists(a: ListNode | None, b: ListNode | None) -> ListNode | None:
    """合并两条按块号非递减排列的空闲链表。

    规格：
      - 返回一条同样按块号非递减排列的链表，包含两条输入链的全部结点（重复块号全部保留）。
      - 可以直接把输入结点重新拼接起来（不必新建结点）。
      - 两条链长度各 0 ~ 10^4，任一条或两条都可能为空；块号是任意整数（可能为负，也可能很大）。

    示例：
      1->2->4  与 1->3->4  → 1->1->2->3->4->4
      7->4096  与 -3->512  → -3->7->512->4096
      空 与 空            → 空（None）
      空 与 0             → 0
    """
    raise TODO("kv.merge_free")


@exercise("kv.merge_free_k")
def merge_k_free_lists(lists: list[ListNode | None]) -> ListNode | None:
    """多个 worker 各自回收了一条按块号非递减排列的空闲链表，把它们合并成一条。

    规格：
      - 返回包含全部结点、按块号非递减排列的链表；重复块号全部保留。
      - ``lists`` 长度 0 ~ 10^4，其中的元素可能为 ``None``（空链）；结点总数不超过 10^4；
        块号在 [-10^4, 10^4] 内。
      - 全部为空（或 ``lists`` 为空列表）时返回 ``None``。
      - 期望复杂度 O(N log k)（N 为结点总数，k 为链表条数）。

    示例：
      [1->4->5, 1->3->4, 2->6]  → 1->1->2->3->4->4->5->6
      []                        → None
      [None]                    → None
    """
    raise TODO("kv.merge_free_k")


@exercise("kv.sort_free")
def sort_free_list(head: ListNode | None) -> ListNode | None:
    """碎片整理：把一条无序的空闲链表按块号升序（非递减）排序。

    规格：
      - 返回排序后的链头；重复块号全部保留。
      - 时间复杂度须为 O(n log n)；链长 0 ~ 5 * 10^4，块号在 [-10^5, 10^5] 内。
      - （进阶：O(1) 额外空间。）

    示例：
      4->2->1->3          → 1->2->3->4
      -1->5->3->4->0      → -1->0->3->4->5
      空                  → 空（None）
    """
    raise TODO("kv.sort_free")


@exercise("kv.drop_double_free")
def drop_double_freed(head: ListNode | None) -> ListNode | None:
    """隔离被重复释放的块：在按块号非递减排列的空闲链表中，凡是出现超过一次的块号，
    其所有结点一个不留地全部移除；只出现一次的块号保留。

    规格：
      - 返回处理后的链头，仍然有序；链可能因此变为空（返回 ``None``）。
      - 链长 0 ~ 10^4；块号是任意整数（可能为负，也可能很大）。

    示例：
      1->2->3->3->4->4->5  → 1->2->5
      998->4096->4096->5000 → 998->5000
      1->1->1->2->3        → 2->3
    """
    raise TODO("kv.drop_double_free")
