"""Framework (M4): crafted traces where the waiting-queue policy decides who meets their deadline.

``deadline_trace`` builds the classic case for earliest-deadline-first:

  * a few long *bulk* jobs (many tokens, loose deadlines) arrive first and fill the queue,
  * a couple of *background* jobs without any deadline arrive with them,
  * then a burst of short *chat* requests arrives, each with a tight deadline.

FCFS serves the bulk and background jobs first, so the chat requests wait behind them and miss their
deadlines. EDF lets the chat requests overtake (their deadlines are earlier) while the bulk jobs still
finish well within their loose deadlines. Every request keeps its own seed, so outputs are identical
under both policies — only the order (and thus the timing) changes.

No exercises are called here; the trace feeds ``nanoserve.index.queue.DeadlineQueue`` via the server.
"""
from __future__ import annotations

from nanoserve.server.request import Request
from nanoserve.server.trace import PROMPTS


def deadline_trace(n_bulk: int = 4, n_chat: int = 8, n_background: int = 2, *, bulk_tokens: int = 48,
                   chat_tokens: int = 8, chat_slack: int = 80, bulk_deadline: int = 400,
                   seed: int = 0) -> list[Request]:
    """Bulk + background jobs at tick 0, then one chat request per tick from tick 1.

    Chat deadline = arrival + chat_tokens + chat_slack. With ``ServerConfig(max_batch=2)`` and the
    defaults, EDF meets every deadline and FCFS misses the chat ones.
    """
    out: list[Request] = []
    for i in range(n_bulk):
        out.append(Request(rid=f"bulk{i:02d}", prompt=PROMPTS[(3 * i) % len(PROMPTS)], arrival=0,
                           max_tokens=bulk_tokens, deadline=bulk_deadline, tenant="batch", seed=seed * 1000 + i))
    for i in range(n_background):
        out.append(Request(rid=f"bg{i:02d}", prompt=PROMPTS[(3 * i + 2) % len(PROMPTS)], arrival=0,
                           max_tokens=bulk_tokens // 2, deadline=None, tenant="batch",
                           seed=seed * 1000 + 100 + i))
    for i in range(n_chat):
        arrival = 1 + i
        out.append(Request(rid=f"chat{i:02d}", prompt=PROMPTS[(5 * i + 1) % len(PROMPTS)], arrival=arrival,
                           max_tokens=chat_tokens, deadline=arrival + chat_tokens + chat_slack, tenant="chat",
                           seed=seed * 1000 + 200 + i))
    return out
