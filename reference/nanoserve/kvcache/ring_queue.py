from __future__ import annotations


# LC 622 Design Circular Queue
class RingQueue:
    def __init__(self, k: int) -> None:
        self.buf = [0] * k
        self.cap = k
        self.head = 0
        self.size = 0

    def enqueue(self, x: int) -> bool:
        if self.size == self.cap:
            return False
        self.buf[(self.head + self.size) % self.cap] = x
        self.size += 1
        return True

    def dequeue(self) -> bool:
        if self.size == 0:
            return False
        self.head = (self.head + 1) % self.cap
        self.size -= 1
        return True

    def front(self) -> int:
        return -1 if self.size == 0 else self.buf[self.head]

    def rear(self) -> int:
        return -1 if self.size == 0 else self.buf[(self.head + self.size - 1) % self.cap]

    def is_empty(self) -> bool:
        return self.size == 0

    def is_full(self) -> bool:
        return self.size == self.cap
