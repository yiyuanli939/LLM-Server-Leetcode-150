"""路由规则中的模型名 glob 匹配。

路由表用带通配符的模式选择后端，例如 ``llama-*-instruct`` 或 ``qwen?-7b``。
请求到来时要判断它的模型名是否与某条规则的模式完整匹配。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("config.glob")
def glob_match(s: str, p: str) -> bool:
    """判断模型名 ``s`` 是否与模式 ``p`` 完整匹配。

    规格：
      - ``s`` 由任意可打印 ASCII 字符组成（大小写字母、数字、``-``、``_``、``.``、``/``、``:`` 等），
        但不含 ``?`` 和 ``*``；``p`` 由同样的字符外加通配符 ``?`` 和 ``*`` 组成（没有转义写法，
        ``p`` 中的 ``?`` ``*`` 永远是通配符）。两者都可以为空串，长度均不超过 2000。
      - ``?`` 恰好匹配任意一个字符；``*`` 匹配任意字符序列（包括空序列）。注意：与 shell 不同，
        ``*`` 和 ``?`` 也能匹配 ``/``。其余字符（包括 ``.``、``-``、``_``）只匹配自身，区分大小写。
      - 必须匹配**整个** ``s``，而不是其中一部分。
      - 不得使用 ``fnmatch``、``re`` 等现成的匹配库。复杂度不超过 O(len(s) * len(p))
        （模式里有很多 ``*`` 时，朴素回溯会指数爆炸）。

    示例：
      >>> glob_match("aa", "a")
      False
      >>> glob_match("aa", "*")
      True
      >>> glob_match("cb", "?a")
      False
      >>> glob_match("llama-3-8b-instruct", "llama-*-instruct")
      True
      >>> glob_match("Qwen2.5-7B_chat:latest", "Qwen?.?-*:*")
      True
      >>> glob_match("Qwen2-7B", "qwen*")
      False
    """
    raise TODO("config.glob")
