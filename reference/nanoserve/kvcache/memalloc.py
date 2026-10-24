from __future__ import annotations


# LC 2502 Design Memory Allocator
class MemoryAllocator:
    def __init__(self, n: int) -> None:
        self.mem = [0] * n

    def allocate(self, size: int, owner: int) -> int:
        run = 0
        for i, o in enumerate(self.mem):
            run = run + 1 if o == 0 else 0
            if run == size:
                start = i - size + 1
                self.mem[start:i + 1] = [owner] * size
                return start
        return -1

    def free(self, owner: int) -> int:
        freed = 0
        for i, o in enumerate(self.mem):
            if o == owner:
                self.mem[i] = 0
                freed += 1
        return freed
