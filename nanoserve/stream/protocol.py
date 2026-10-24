"""流式协议的分帧编解码。

服务端向客户端推送的是一串文本片段（chunk），但底层通道只能传输单个字符串。
本文件负责把片段列表打包成一个字符串，并在另一端无损地还原成原来的列表——
片段内容是模型输出，可能包含任何字符，因此不能靠"选一个不会出现的分隔符"来解决。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("stream.frame_codec")
class FrameCodec:
    """流式协议分帧：把任意字符串列表编码成一个字符串，并能无损解码。

    规格：
      - encode(chunks)：chunks 是字符串列表，可以为空列表；每个字符串可以为空串，
        可以包含任意 Unicode 字符（数字、'#'、','、换行、中文、emoji……）。返回一个 str。
      - decode(data)：data 一定是 encode 的输出；返回与原 chunks 完全相等的列表
        （长度、顺序、每个元素都相同）。
      - 编码格式自定，只要求 decode(encode(x)) == x 对所有合法输入成立。
      - 不允许使用 pickle / json / repr+eval 等现成序列化手段；codec 不应依赖实例状态
        （用一个实例 encode、另一个实例 decode 也必须正确）。
      - 复杂度：编码与解码均为 O(总字符数)。

    示例：
      >>> c = FrameCodec()
      >>> c.decode(c.encode(["Hello", "World"]))
      ['Hello', 'World']
      >>> c.decode(c.encode([]))
      []
    """

    def encode(self, chunks: list[str]) -> str:
        raise TODO("stream.frame_codec")

    def decode(self, data: str) -> list[str]:
        raise TODO("stream.frame_codec")
