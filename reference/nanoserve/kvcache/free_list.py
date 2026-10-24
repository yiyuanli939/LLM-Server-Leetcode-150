from __future__ import annotations

import heapq

from nanoserve.common.nodes import ListNode


# LC 21 Merge Two Sorted Lists
def merge_free_lists(a: ListNode | None, b: ListNode | None) -> ListNode | None:
    dummy = ListNode()
    tail = dummy
    while a is not None and b is not None:
        if a.val <= b.val:
            tail.next, a = a, a.next
        else:
            tail.next, b = b, b.next
        tail = tail.next
    tail.next = a if a is not None else b
    return dummy.next


# LC 23 Merge k Sorted Lists
def merge_k_free_lists(lists: list[ListNode | None]) -> ListNode | None:
    heap = [(node.val, i, node) for i, node in enumerate(lists) if node is not None]
    heapq.heapify(heap)
    dummy = ListNode()
    tail = dummy
    while heap:
        _, i, node = heapq.heappop(heap)
        tail.next = node
        tail = node
        if node.next is not None:
            heapq.heappush(heap, (node.next.val, i, node.next))
    tail.next = None
    return dummy.next


# LC 148 Sort List (top-down merge sort)
def sort_free_list(head: ListNode | None) -> ListNode | None:
    if head is None or head.next is None:
        return head
    slow, fast = head, head.next
    while fast is not None and fast.next is not None:
        slow = slow.next
        fast = fast.next.next
    mid = slow.next
    slow.next = None
    return merge_free_lists(sort_free_list(head), sort_free_list(mid))


# LC 82 Remove Duplicates from Sorted List II
def drop_double_freed(head: ListNode | None) -> ListNode | None:
    dummy = ListNode(0, head)
    prev = dummy
    cur = head
    while cur is not None:
        if cur.next is not None and cur.next.val == cur.val:
            v = cur.val
            while cur is not None and cur.val == v:
                cur = cur.next
            prev.next = cur
        else:
            prev = cur
            cur = cur.next
    return dummy.next
