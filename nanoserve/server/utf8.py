"""流式传输的 UTF-8 合法性检查。

服务器按字节把生成结果切包推给客户端，一个多字节字符可能被切在两个包之间。
客户端先把收到的字节攒在缓冲区里，只有当缓冲区整体构成合法的 UTF-8 编码序列时
才解码出来做预览；否则继续等下一个包。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("server.utf8_ok")
def utf8_valid(data: list[int]) -> bool:
    """判断字节序列 data 是否整体是一段合法的 UTF-8 编码（由若干个完整字符依次拼成）。

    规格：
      - data[i] 是一个字节，取值 0..255；1 <= len(data)。
      - 每个字符占 1~4 个字节，按首字节的高位判定长度：
          1 字节：0xxxxxxx
          2 字节：110xxxxx 10xxxxxx
          3 字节：1110xxxx 10xxxxxx 10xxxxxx
          4 字节：11110xxx 10xxxxxx 10xxxxxx 10xxxxxx
        即首字节之后必须紧跟恰好 (长度 - 1) 个形如 10xxxxxx 的后续字节。
      - 以 10xxxxxx 开头的字节不能作为字符的首字节；以 11111xxx 开头的字节在任何位置都不合法。
      - 序列末尾若有一个字符的后续字节不够（被截断），整体不合法。
      - 只检查上述位模式：**不**检查过长编码（overlong）、代理区码点或码点上限，
        例如 [0xC0, 0x80] 按本规格是合法的。
      - 合法返回 True，否则返回 False。复杂度 O(n)。

    示例：
      >>> utf8_valid([197, 130, 1])            # 11000101 10000010 00000001：一个 2 字节字符 + 一个 1 字节字符
      True
      >>> utf8_valid([235, 140, 4])            # 11101011 10001100 00000100：3 字节字符的第 3 个字节不是 10xxxxxx
      False
      >>> utf8_valid([0xE4, 0xBD])             # "你" 的 3 字节编码只到了 2 个字节
      False
    """
    raise TODO("server.utf8_ok")
