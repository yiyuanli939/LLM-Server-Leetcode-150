"""固定容量的环形请求队列。

块管理器在等待显存时把请求暂存在一个预先分配好、容量固定的环形缓冲区里：
入队写到队尾，出队从队头取，满了就拒绝，不做任何动态扩容。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("kv.ring_queue")
class RingQueue:
    """容量固定为 k 的先进先出环形队列（用定长数组 + 头尾指针实现，不要用动态扩容的结构）。

    规格：
      - ``RingQueue(k)``：容量 ``k >= 1``。
      - ``enqueue(x)``：未满则把 x 放到队尾并返回 True；已满返回 False（队列不变）。
      - ``dequeue()``：非空则移除队头元素并返回 True；为空返回 False。
      - ``front()``：返回队头元素；队列为空返回 -1。
      - ``rear()``：返回队尾元素；队列为空返回 -1。
      - ``is_empty()`` / ``is_full()``：队列是否为空 / 是否已满。
      - 入队的值为非负整数；所有操作均为 O(1)。

    示例：
      >>> q = RingQueue(3)
      >>> q.enqueue(1), q.enqueue(2), q.enqueue(3), q.enqueue(4)
      (True, True, True, False)
      >>> q.rear(), q.is_full(), q.dequeue(), q.enqueue(4), q.rear()
      (3, True, True, True, 4)
    """

    def __init__(self, k: int) -> None:
        raise TODO("kv.ring_queue")

    def enqueue(self, x: int) -> bool:
        raise TODO("kv.ring_queue")

    def dequeue(self) -> bool:
        raise TODO("kv.ring_queue")

    def front(self) -> int:
        raise TODO("kv.ring_queue")

    def rear(self) -> int:
        raise TODO("kv.ring_queue")

    def is_empty(self) -> bool:
        raise TODO("kv.ring_queue")

    def is_full(self) -> bool:
        raise TODO("kv.ring_queue")
