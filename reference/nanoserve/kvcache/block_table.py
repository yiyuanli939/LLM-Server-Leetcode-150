from __future__ import annotations

from nanoserve.common.nodes import ListNode, RandomListNode


# LC 138 Copy List with Random Pointer
def fork_chain(head: RandomListNode | None) -> RandomListNode | None:
    clones: dict[int, RandomListNode] = {}
    cur = head
    while cur is not None:
        clones[id(cur)] = RandomListNode(cur.val)
        cur = cur.next
    cur = head
    while cur is not None:
        c = clones[id(cur)]
        c.next = clones[id(cur.next)] if cur.next is not None else None
        c.random = clones[id(cur.random)] if cur.random is not None else None
        cur = cur.next
    return clones[id(head)] if head is not None else None


# LC 141 Linked List Cycle
def has_cycle(head: ListNode | None) -> bool:
    slow = fast = head
    while fast is not None and fast.next is not None:
        slow = slow.next
        fast = fast.next.next
        if slow is fast:
            return True
    return False


# LC 86 Partition List
def partition_by_heat(head: ListNode | None, x: int) -> ListNode | None:
    lo_dummy, hi_dummy = ListNode(), ListNode()
    lo, hi = lo_dummy, hi_dummy
    while head is not None:
        if head.val < x:
            lo.next = head
            lo = head
        else:
            hi.next = head
            hi = head
        head = head.next
    hi.next = None
    lo.next = hi_dummy.next
    return lo_dummy.next
