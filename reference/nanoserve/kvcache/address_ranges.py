"""Reference: kv.address_ranges."""
from __future__ import annotations

import bisect


# LC 715 Range Module
class AddressRanges:
    """Sorted boundary list: addresses in [b[2i], b[2i+1]) are allocated, disjoint and non-touching."""

    def __init__(self) -> None:
        self.b: list[int] = []

    def _replace(self, left: int, right: int, keep_inside: bool) -> None:
        # Boundaries strictly inside the edited span disappear; `left` / `right` become
        # boundaries only where the covered/uncovered state actually changes.
        i = bisect.bisect_left(self.b, left)
        j = bisect.bisect_right(self.b, right)
        new: list[int] = []
        if (i % 2 == 0) == keep_inside:  # left falls outside (add) / inside (remove) a range
            new.append(left)
        if (j % 2 == 0) == keep_inside:
            new.append(right)
        self.b[i:j] = new

    def add_range(self, left: int, right: int) -> None:
        self._replace(left, right, keep_inside=True)

    def remove_range(self, left: int, right: int) -> None:
        self._replace(left, right, keep_inside=False)

    def query_range(self, left: int, right: int) -> bool:
        i = bisect.bisect_right(self.b, left)
        j = bisect.bisect_left(self.b, right)
        return i == j and i % 2 == 1
