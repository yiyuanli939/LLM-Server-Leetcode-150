"""Framework: multi-device placement of a compiled IR plan (M5).

A deployment is ``n`` devices (1-based ids) joined by *directed* links ``(u, v, ms)``: copying a
tensor from u to v takes ``ms``. Placing the model works like this:

  1. **islands** — devices that are linked directly or through other devices form one island; only an
     island can act as one model-parallel group. The island count comes from the link adjacency
     matrix (``count_device_groups``). Membership uses the same exercise as an oracle: devices i and
     j are already in one island iff adding a direct i–j link would not reduce the count.
  2. **weight broadcast** — the checkpoint is read on one *host* device and broadcast over the links
     to every device of the island (``broadcast_latency``). We try every device as host and keep the
     fastest; a device that cannot reach the whole island over directed links is not a valid host.
  3. **op placement** — the n-gram lookups (the heavy, independent ops) are spread over the island:
     largest cost first, each onto the least-loaded device, preferring devices other than the host
     (the host runs the floor / sum / log tail). A scale op follows its lookup.
  4. **estimate** — ops placed on the same device run one after another (in schedule order), so the
     estimated step latency is the critical path of the dependency graph *plus* those per-device
     chains (``Plan.critical_path`` -> ``critical_path_time``). Transfer time between devices is
     ignored in this estimate; the link latencies are used for the one-off weight broadcast.

Exercises this file calls: ir.device_groups, ir.op_latency (and ir.critical_path via ``Plan``).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from nanoserve.ir.compiler import Plan
from nanoserve.ir.latency import broadcast_latency
from nanoserve.ir.topology import count_device_groups

Link = tuple[int, int, int]


@dataclass
class Topology:
    n: int                 # devices 1..n
    links: list[Link]      # (u, v, ms): directed link u -> v

    def __post_init__(self) -> None:
        if self.n < 1:
            raise ValueError("need at least one device")
        seen: set[tuple[int, int]] = set()
        for u, v, w in self.links:
            if not (1 <= u <= self.n and 1 <= v <= self.n) or u == v or w < 0:
                raise ValueError(f"bad link {(u, v, w)}: devices are 1..{self.n}, no self links, w >= 0")
            if (u, v) in seen:
                raise ValueError(f"duplicate link {u}->{v}")
            seen.add((u, v))

    def matrix(self, extra: tuple[int, int] | None = None) -> list[list[int]]:
        """Symmetric 0/1 "linked" matrix (0-based, diagonal 1); ``extra`` adds one direct link."""
        m = [[int(i == j) for j in range(self.n)] for i in range(self.n)]
        pairs = [(u, v) for u, v, _ in self.links] + ([extra] if extra else [])
        for u, v in pairs:
            m[u - 1][v - 1] = m[v - 1][u - 1] = 1
        return m

    def group_count(self) -> int:
        return count_device_groups(self.matrix())

    def islands(self) -> list[list[int]]:
        """Device ids of every island, each sorted, islands ordered by their smallest device."""
        base = self.group_count()
        islands: list[list[int]] = []
        for d in range(1, self.n + 1):
            for isl in islands:
                # a direct link d - rep merges two islands (count drops) unless they are one already
                if count_device_groups(self.matrix((d, isl[0]))) == base:
                    isl.append(d)
                    break
            else:
                islands.append([d])
        assert len(islands) == base
        return islands

    def broadcast_time(self, island: Sequence[int], host: int) -> int:
        """Time until every device of ``island`` holds data that starts on ``host`` (-1: unreachable)."""
        local = {d: i + 1 for i, d in enumerate(island)}   # renumber the island 1..m
        edges = [[local[u], local[v], w] for u, v, w in self.links if u in local and v in local]
        return broadcast_latency(edges, len(island), local[host])


@dataclass
class Placement:
    groups: int                     # number of islands in the deployment
    island: list[int]               # devices that host the model
    host: int                       # device that reads the checkpoint
    broadcast: int                  # weight broadcast time from host to the island
    broadcast_by_host: dict[int, int]
    device_of: dict[str, int]       # op name -> device
    latency: int                    # estimated step latency on this placement
    parallel: int                   # critical path with unlimited devices
    serial: int                     # everything on one device
    load: dict[int, int] = field(default_factory=dict)   # device -> total op cost

    def summary(self) -> list[str]:
        lines = [f"{self.groups} device island(s); model placed on island {self.island} "
                 f"(host {self.host}, weight broadcast {self.broadcast} ms)"]
        hosts = ", ".join(f"{d}:{t if t >= 0 else 'unreachable'}" for d, t in self.broadcast_by_host.items())
        lines.append(f"  broadcast time by host  {hosts}")
        for d in self.island:
            ops = [name for name, dev in self.device_of.items() if dev == d]
            lines.append(f"  device {d}: load {self.load.get(d, 0):>2}  {' '.join(ops) or '-'}")
        lines.append(f"  step latency estimate {self.latency}  (1 device: {self.serial}, "
                     f"unlimited devices: {self.parallel})")
        return lines


def choose_island(topo: Topology) -> tuple[list[int], int, int, dict[int, int]]:
    """Largest island that has a valid host; ties -> faster broadcast, then lower device id."""
    best: tuple | None = None
    for isl in topo.islands():
        times = {d: topo.broadcast_time(isl, d) for d in isl}
        ok = [(t, d) for d, t in times.items() if t >= 0]
        if not ok:
            continue
        t, host = min(ok)
        key = (-len(isl), t, isl[0])
        if best is None or key < best[0]:
            best = (key, isl, host, t, times)
    if best is None:
        raise ValueError("no island has a device that can broadcast the weights to all its members")
    _, isl, host, t, times = best
    return isl, host, t, times


def place(plan: Plan, topo: Topology) -> Placement:
    island, host, bcast, times = choose_island(topo)
    ops = plan.ops
    load = {d: 0 for d in island}
    device_of: dict[str, int] = {}
    lookups = sorted((i for i, op in enumerate(ops) if op.kind == "lookup"), key=lambda i: (-ops[i].cost, i))
    for i in lookups:   # heaviest first onto the least-loaded device; ties: keep the host free
        d = min(island, key=lambda dev: (load[dev], dev == host, dev))
        device_of[ops[i].out] = d
        load[d] += ops[i].cost
    for op in ops:
        if op.out in device_of:
            continue
        src = op.inputs[0]
        d = device_of.get(src, host) if op.kind == "scale" else host
        device_of[op.out] = d
        load[d] += op.cost
    # same device -> run one after another in schedule order
    chains: list[tuple[int, int]] = []
    for d in island:
        seq = [i for i in plan.order if device_of[ops[i].out] == d]
        chains += list(zip(seq, seq[1:]))
    return Placement(
        groups=topo.group_count(), island=island, host=host, broadcast=bcast, broadcast_by_host=times,
        device_of={op.out: device_of[op.out] for op in ops}, latency=plan.critical_path(chains),
        parallel=plan.critical_path(), serial=plan.serial_time(), load=load,
    )


# A small default deployment for demos: a 4-device island with asymmetric links and a 2-device island.
DEFAULT_TOPOLOGY = Topology(6, [
    (1, 2, 2), (2, 1, 2), (2, 3, 1), (3, 2, 1), (3, 4, 3), (4, 3, 3), (1, 4, 5),
    (5, 6, 1), (6, 5, 1),
])
