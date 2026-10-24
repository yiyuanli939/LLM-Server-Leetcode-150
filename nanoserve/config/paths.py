"""模型权重路径处理。

配置中给出的模型路径可能是手写的，带有多余斜杠、``.`` 和 ``..``；加载权重前要先把它
规范化成唯一的标准形式，便于做缓存键和去重。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("config.norm_path")
def normalize_path(path: str) -> str:
    """把一个 Unix 风格的绝对路径规范化。

    规格：
      - 输入 path 以 ``'/'`` 开头；``'/'`` 是唯一的分隔符，其余字符可以是任意可打印 ASCII 字符
        （大小写字母、数字、``'.'``、``'_'``、``'-'``、``':'`` 等，不含空白），按字面原样保留。
      - 规则：``'.'`` 表示当前目录（忽略）；``'..'`` 表示上一级目录（在根目录时保持在根）；
        连续多个 ``'/'`` 视为一个；其它任何由点组成的名字（如 ``'...'``、``'....'``）
        都是普通目录名。
      - 输出：以单个 ``'/'`` 开头；目录之间恰好一个 ``'/'``；不以 ``'/'`` 结尾
        （除非结果就是根目录 ``'/'``）；不含 ``'.'`` 或 ``'..'`` 组件。

    示例：
      >>> normalize_path("/home//foo/")
      '/home/foo'
      >>> normalize_path("/../")
      '/'
      >>> normalize_path("/.../a/../b/c/../d/./")
      '/.../b/d'
      >>> normalize_path("/models/./llama-3_8B/../qwen2.5-7b/")
      '/models/qwen2.5-7b'
    """
    raise TODO("config.norm_path")
