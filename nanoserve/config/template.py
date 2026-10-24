"""配置模板展开。

配置文件里常要写重复结构（例如每层一样的设置），模板语法允许把重复片段折叠成 k[片段]，
加载配置时先把模板完整展开。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("config.expand")
def expand_template(s: str) -> str:
    """展开模板字符串：``k[片段]`` 表示片段重复 k 次，可以任意嵌套。

    规格：
      - 输入由数字、方括号 ``[`` ``]`` 和其它任意可打印 ASCII 字符组成（大小写字母、``,``、``-``、
        ``_``、``.``、``:``、空格等）。除数字和方括号以外的字符都是普通内容，原样保留。
      - 保证格式合法：数字只会作为重复次数出现，且其后紧跟 ``[``；每个 ``[`` 前面都紧挨着它的
        重复次数；方括号严格配对；k 为正整数，可以有多位（如 ``10[a]``）。
      - 普通字符不会出现在数字的位置上（例如不会有 ``3a`` 或 ``2[4]`` 这样的输入）。
      - 返回完全展开后的字符串；输入不含任何方括号时原样返回。

    示例：
      >>> expand_template("3[a]2[bc]")
      'aaabcbc'
      >>> expand_template("3[a2[c]]")
      'accaccacc'
      >>> expand_template("2[abc]3[cd]ef")
      'abcabccdcdcdef'
      >>> expand_template("2[gpu-A,]cpu_b")
      'gpu-A,gpu-A,cpu_b'
    """
    raise TODO("config.expand")
