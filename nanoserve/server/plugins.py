"""Framework: plug-in interfaces between the server core (M2) and later milestones.

  * ``KVBackend``          — KV-cache block accounting (M3: nanoserve.kvcache.manager.BlockManager)
  * ``PrefixCacheBackend`` — prompt prefix cache       (M4: nanoserve.prefix.cache.PrefixCache)
  * ``WaitingQueue``       — ordering of waiting requests (FCFS here; M4: nanoserve.index.queue.DeadlineQueue)

The server only talks to these interfaces, so each milestone can be swapped in independently.
The ``Null*`` / ``FCFSQueue`` defaults below are what the server uses when a feature is off.
"""
from __future__ import annotations

from collections import deque
from typing import Iterator, Protocol, runtime_checkable

from nanoserve.server.request import Request


@runtime_checkable
class KVBackend(Protocol):
    def can_admit(self, req: Request, now: int) -> bool:
        """Is there room to admit ``req`` (its prompt + at least one new token) right now?"""

    # Optional: ``can_ever_fit(req) -> bool`` — could ``req`` finish if it had the whole cache to
    # itself? The server rejects requests that can't (see Server._admit_waiting); backends without
    # it are assumed to fit everything.

    def on_admit(self, req: Request, now: int) -> None:
        """Allocate blocks for the request's prompt."""

    def on_token(self, req: Request, now: int) -> bool:
        """One more token was generated. Return False if it can't be stored (→ server preempts)."""

    def on_finish(self, req: Request, now: int) -> None:
        """Release everything the request holds (also called on preemption)."""

    def report(self) -> dict:
        ...


@runtime_checkable
class PrefixCacheBackend(Protocol):
    def match(self, prompt: str) -> int:
        """Number of leading prompt characters already cached."""

    def insert(self, prompt: str) -> None:
        ...

    def report(self) -> dict:
        ...


@runtime_checkable
class WaitingQueue(Protocol):
    def push(self, req: Request) -> None: ...
    def push_front(self, req: Request) -> None: ...  # preempted requests go back first
    def peek(self) -> Request | None: ...
    def pop(self) -> Request: ...
    def remove(self, req: Request) -> None: ...
    def __len__(self) -> int: ...
    def __iter__(self) -> Iterator[Request]: ...


class NullKV:
    def can_admit(self, req: Request, now: int) -> bool:
        return True

    def can_ever_fit(self, req: Request) -> bool:
        return True

    def on_admit(self, req: Request, now: int) -> None:
        pass

    def on_token(self, req: Request, now: int) -> bool:
        return True

    def on_finish(self, req: Request, now: int) -> None:
        pass

    def report(self) -> dict:
        return {}


class NullPrefixCache:
    def match(self, prompt: str) -> int:
        return 0

    def insert(self, prompt: str) -> None:
        pass

    def report(self) -> dict:
        return {}


class FCFSQueue:
    def __init__(self) -> None:
        self._q: deque[Request] = deque()

    def push(self, req: Request) -> None:
        self._q.append(req)

    def push_front(self, req: Request) -> None:
        self._q.appendleft(req)

    def peek(self) -> Request | None:
        return self._q[0] if self._q else None

    def pop(self) -> Request:
        return self._q.popleft()

    def remove(self, req: Request) -> None:
        self._q.remove(req)

    def __len__(self) -> int:
        return len(self._q)

    def __iter__(self) -> Iterator[Request]:
        return iter(list(self._q))
