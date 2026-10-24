"""前缀缓存的字典树。

前缀缓存需要快速回答两类问题："这条完整 prompt 是否已经缓存过？" 以及 "有没有任何已缓存的
prompt 以这段文本开头？"。本文件实现最基础的逐字符字典树，后续的 Radix Tree 在它之上压缩路径。
键可以由任意字符组成：前缀缓存把每个 token 映射成一个字符，"按 token 匹配前缀"就成了普通的字符串前缀问题。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("prefix.trie")
class PrefixTrie:
    """前缀缓存的字典树：记录已缓存的完整键，并支持前缀查询。

    规格：
      - ``insert(word)``：把 ``word`` 作为一个完整键加入；重复插入同一个键无副作用。
      - ``search(word)``：当且仅当 ``word`` 曾被 ``insert`` 作为**完整键**插入时返回 True；
        只是某个键的前缀（但自身未被插入）返回 False。
      - ``starts_with(prefix)``：当且仅当存在至少一个已插入的键以 ``prefix`` 开头时返回 True
        （键本身等于 prefix 也算）。
      - 所有字符串均为非空字符串，可以包含**任意字符**（大小写字母、数字、空格、标点、换行、任意 Unicode
        字符，包括 ``$``、``#`` 这类常被拿来当哨兵的字符）；按字符逐个比较，区分大小写。
      - 三个操作的时间复杂度都应为 O(字符串长度)，与已插入键的数量无关。

    示例：
      >>> t = PrefixTrie(); t.insert("apple"); t.search("apple")
      True
      >>> t.search("app"), t.starts_with("app")
      (False, True)
      >>> t.insert("app"); t.search("app")
      True
      >>> t.insert("Sys: héllo, wörld! €5"); t.starts_with("Sys: hé"), t.search("Sys: héllo"), t.starts_with("sys")
      (True, False, False)
    """

    def __init__(self) -> None:
        raise TODO("prefix.trie")

    def insert(self, word: str) -> None:
        raise TODO("prefix.trie")

    def search(self, word: str) -> bool:
        raise TODO("prefix.trie")

    def starts_with(self, prefix: str) -> bool:
        raise TODO("prefix.trie")
