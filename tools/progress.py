#!/usr/bin/env python3
"""Progress dashboard.

    python tools/progress.py              # 全部里程碑，无剧透
    python tools/progress.py --ms M3 -v   # 只看 M3，并列出每个练习
    python tools/progress.py --reveal     # 额外显示已完成练习对应的 LeetCode 题
    python tools/progress.py --reveal-all # 显示全部对应关系（完全剧透）
    python tools/progress.py --reference  # 用参考解跑（维护者自检）

Status per exercise: ✅ all its tests pass · ⬜ TODO (still raises NotImplementedError) · ❌ some test fails
"""
from __future__ import annotations

import argparse
import contextlib
import io
import os
import sys
from collections import defaultdict
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent


class Collector:
    def __init__(self) -> None:
        self.ex: dict[str, list[str]] = defaultdict(list)
        self.ms: dict[str, list[str]] = defaultdict(list)
        self.collect_errors: list[str] = []

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(self, item, call):
        outcome = yield
        rep = outcome.get_result()
        if rep.when == "call" or (rep.when == "setup" and not rep.passed):
            if rep.passed:
                status = "pass"
            elif rep.skipped:
                status = "skip"
            elif call.excinfo is not None and call.excinfo.errisinstance(NotImplementedError):
                status = "todo"
            else:
                status = "fail"
            m = item.get_closest_marker("exercise")
            if m is not None:
                self.ex[m.args[0]].append(status)
            m = item.get_closest_marker("milestone")
            if m is not None:
                self.ms[m.args[0]].append(status)

    def pytest_collectreport(self, report):
        if report.failed:
            self.collect_errors.append(str(report.nodeid))


def summarize(statuses: list[str]) -> str:
    if not statuses:
        return "notest"
    if all(s == "pass" for s in statuses):
        return "pass"
    if any(s == "fail" for s in statuses):
        return "fail"
    if any(s == "todo" for s in statuses):
        return "todo"
    return "fail"


ICON = {"pass": "✅", "todo": "⬜", "fail": "❌", "notest": "❔"}


def bar(done: int, total: int, width: int = 20) -> str:
    filled = round(width * done / total) if total else 0
    return "█" * filled + "░" * (width - filled)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ms", help="only this milestone (M1..M7, X)")
    ap.add_argument("-v", "--verbose", action="store_true", help="list every exercise")
    ap.add_argument("--reveal", action="store_true", help="show LeetCode mapping for finished exercises")
    ap.add_argument("--reveal-all", action="store_true", help="show LeetCode mapping for everything")
    ap.add_argument("--reference", action="store_true", help="run against reference solutions")
    args = ap.parse_args()

    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    if args.reference:
        os.environ["NANOSERVE_REFERENCE"] = "1"

    meta = yaml.safe_load((ROOT / "exercises.yaml").read_text())
    spoilers = {}
    if args.reveal or args.reveal_all:
        spoilers = yaml.safe_load((ROOT / ".spoilers" / "lc_map.yaml").read_text())

    col = Collector()
    targets = ["tests"]
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        pytest.main(["-q", "--tb=no", "--no-header", "-p", "no:cacheprovider", "--continue-on-collection-errors", *targets], plugins=[col])

    if col.collect_errors:
        print("⚠️  有测试文件无法导入（通常是语法错误）：")
        for e in col.collect_errors:
            print("   ", e)
        print()

    by_ms: dict[str, list[dict]] = defaultdict(list)
    for e in meta["exercises"]:
        by_ms[e["ms"]].append(e)

    totals = {"lc150": [0, 0], "other": [0, 0]}
    for ms, title in meta["milestones"].items():
        if args.ms and ms != args.ms:
            continue
        exs = by_ms.get(ms, [])
        res = {e["id"]: summarize(col.ex.get(e["id"], [])) for e in exs}
        done = sum(1 for r in res.values() if r == "pass")
        for e in exs:
            t = totals[e.get("track", "lc150")]
            t[0] += res[e["id"]] == "pass"
            t[1] += 1
        integ = col.ms.get(ms)
        integ_s = "  集成测试 " + ICON[summarize(integ)] if integ else ""
        print(f"{ms:<3} {bar(done, len(exs))} {done:>3}/{len(exs):<3} {title}{integ_s}")
        if args.verbose or args.ms or args.reveal or args.reveal_all:
            for e in exs:
                r = res[e["id"]]
                tag = "★" if e.get("track") == "lc150" else " "
                line = f"   {tag} {ICON[r]} {e['id']:<26} {e['module']}::{e['symbol']}"
                show = args.reveal_all or (args.reveal and r == "pass")
                if show and e["id"] in spoilers:
                    s_ = spoilers[e["id"]]
                    line += f"   → LC {s_['lc']} {s_['title']}"
                print(line)
    if not args.ms:
        a, b = totals["lc150"], totals["other"]
        print()
        print(f"总计 {a[0] + b[0]}/{a[1] + b[1]}    其中 Top Interview 150 ★ {a[0]}/{a[1]}，其它 LeetCode {b[0]}/{b[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
