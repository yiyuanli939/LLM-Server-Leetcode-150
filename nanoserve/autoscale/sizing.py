"""容量规划：求最小资源配置。

自动扩缩容经常要回答"至少需要多少"：至少多大的周期吞吐、多快的服务速率、多长的时间才能完成一批工作。
这几类问题都具有单调性——资源越多越容易满足——而答案的取值范围可能非常大。
"""
from __future__ import annotations

from nanoserve._exercise import TODO, exercise


@exercise("autoscale.min_throughput")
def min_throughput(work: list[int], days: int) -> int:
    """一批任务必须按顺序在 ``days`` 个周期内处理完，求每个周期所需的最小吞吐上限。

    规格：
      - ``work[i]`` 是第 i 个任务的工作量（1 <= work[i] <= 10^9）。任务必须按下标顺序处理：
        每个周期处理连续的一段任务，一个任务不能拆到两个周期里。
      - 每个周期处理的总工作量不得超过吞吐上限 C（所有周期的 C 相同）。
      - 返回能在至多 ``days`` 个周期内处理完全部任务的最小整数 C。
      - 1 <= days <= len(work) <= 5*10^4。
      - 复杂度：O(n log(sum(work)))；答案可能很大，逐个尝试 C 会超时。

    示例：
      >>> min_throughput([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 5)
      15
      >>> min_throughput([3, 2, 2, 4, 1, 4], 3)
      6
      >>> min_throughput([1, 2, 3, 1, 1], 4)
      3
    """
    raise TODO("autoscale.min_throughput")


@exercise("autoscale.min_rate")
def min_drain_rate(queues: list[int], hours: int) -> int:
    """在 ``hours`` 个时间片内清空所有队列所需的最小服务速率。

    规格：
      - ``queues[i]`` 是第 i 个队列中积压的请求数（1 <= queues[i] <= 10^9，1 <= len(queues) <= 10^4）。
      - 每个时间片只能选择**一个**队列服务，从中取出至多 rate 个请求；若该队列剩余不足 rate 个，
        取完即止，这个时间片剩余的能力浪费掉（不能转去服务别的队列）。
      - 返回能在至多 ``hours`` 个时间片内清空全部队列的最小正整数 rate。
      - 保证 len(queues) <= hours <= 10^9，因此答案一定存在。
      - 复杂度：O(n log(max(queues)))；逐个尝试 rate 会超时。

    示例：
      >>> min_drain_rate([3, 6, 7, 11], 8)
      4
      >>> min_drain_rate([30, 11, 23, 4, 20], 5)
      30
      >>> min_drain_rate([30, 11, 23, 4, 20], 6)
      23
    """
    raise TODO("autoscale.min_rate")


@exercise("autoscale.min_time")
def min_time_for(per_request_time: list[int], total: int) -> int:
    """异构 worker 并行处理请求，求完成 ``total`` 个请求所需的最短时间。

    规格：
      - ``per_request_time[i]`` 是 worker i 完成一个请求所需的时间
        （1 <= per_request_time[i] <= 10^7，1 <= len(per_request_time) <= 10^5）。
      - 每个 worker 从时刻 0 开始一个接一个、不间断地处理请求，彼此独立；因此到时刻 T 为止，
        worker i 恰好完成 ``T // per_request_time[i]`` 个请求。
      - 返回使所有 worker 完成的请求总数 >= ``total`` 的最小整数 T。1 <= total <= 10^7。
      - 复杂度：O(n log(min(per_request_time) * total))；答案可达 10^14，逐个尝试 T 会超时。

    示例：
      >>> min_time_for([1, 2, 3], 5)
      3
      >>> min_time_for([2], 1)
      2
    """
    raise TODO("autoscale.min_time")
