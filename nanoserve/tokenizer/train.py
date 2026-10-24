"""词表训练的辅助统计。

训练分词器时，需要从语料切出的大量候选片段中挑出最常出现的若干个，作为新的多字符 token
加入词表。本文件实现"按出现频率选出前 k 个片段"这一步。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("tok.top_pieces")
def top_k_pieces(pieces: list[str], k: int) -> list[str]:
    """训练词表：从候选片段序列中选出出现次数最多的 k 个不同片段。

    规格：
      - pieces：语料切出的候选片段序列，可重复；1 <= len(pieces)。
      - k：1 <= k <= pieces 中不同片段的个数。
      - 返回出现次数最多的 k 个不同片段，顺序任意。
      - 保证答案唯一（即第 k 名与第 k+1 名的出现次数不会相同）。
      - 复杂度要求优于 O(n log n)（n 为 len(pieces)），例如 O(n log k) 或 O(n)。

    示例：
      >>> sorted(top_k_pieces(["a", "a", "a", "b", "b", "c"], 2))
      ['a', 'b']
      >>> top_k_pieces(["the"], 1)
      ['the']
    """
    raise TODO("tok.top_pieces")
