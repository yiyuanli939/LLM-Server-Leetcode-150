#!/usr/bin/env python3
"""Maintainer check: is every exercise actually exercised by the engine's integration tests?

Runs tests/domain/ under coverage in reference mode and reports, per exercise, whether any line of
its reference implementation executed. Needs `pip install coverage` and the reference/ package.

    python tools/callsites.py            # table of unexercised exercises; exit 1 if any
"""
from __future__ import annotations

import ast
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    os.chdir(ROOT)
    data = Path(tempfile.mkdtemp()) / ".coverage"
    env = dict(os.environ, NANOSERVE_REFERENCE="1", COVERAGE_FILE=str(data))
    subprocess.run([sys.executable, "-m", "coverage", "run", "--source=reference", "-m", "pytest", "-q",
                    "-p", "no:cacheprovider", "tests/domain"], env=env, check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    import coverage
    cov = coverage.Coverage(data_file=str(data))
    cov.load()
    cd = cov.get_data()
    meta = yaml.safe_load((ROOT / "exercises.yaml").read_text())
    missing = []
    for e in meta["exercises"]:
        path = ROOT / "reference" / e["module"]
        executed = set(cd.lines(str(path.resolve())) or [])
        tree = ast.parse(path.read_text())
        node = next((n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name == e["symbol"]), None)
        if node is None:
            missing.append((e["ms"], e["id"], "symbol not found"))
            continue
        body_lines = set()
        for sub in ast.walk(node):
            if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for stmt in sub.body:
                    body_lines.update(range(stmt.lineno, stmt.end_lineno + 1))
        if not (body_lines & executed):
            missing.append((e["ms"], e["id"], f"{e['module']}::{e['symbol']}"))
    total = len(meta["exercises"])
    print(f"exercised by tests/domain: {total - len(missing)}/{total}")
    for ms, eid, where in missing:
        print(f"  {ms} {eid:<26} {where}")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
