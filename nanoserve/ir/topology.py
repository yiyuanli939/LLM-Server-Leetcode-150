"""设备互联拓扑分析。

多卡部署时先要知道哪些设备彼此（直接或经由其他设备）互联，互联的设备才能组成一个张量并行组。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("ir.device_groups")
def count_device_groups(linked: list[list[int]]) -> int:
    """给定设备互联邻接矩阵，返回互联组（连通分量）的个数。

    规格：
      - ``linked`` 为 n×n 的 0/1 矩阵（n >= 1）：``linked[i][j] == 1`` 表示设备 i 与 j 直接互联。
        保证矩阵对称，且 ``linked[i][i] == 1``。
      - 直接或间接（经过若干台设备）互联的设备属于同一组；返回组数。
      - 建议用并查集实现。

    示例：
      >>> count_device_groups([[1, 1, 0], [1, 1, 0], [0, 0, 1]])
      2
      >>> count_device_groups([[1, 0, 0], [0, 1, 0], [0, 0, 1]])
      3
    """
    raise TODO("ir.device_groups")
