"""Exercise registry.

Every function/class you are asked to implement is decorated with ``@exercise("<id>")``.
The decorator does two things:

1. registers the object under its id, so ``tools/progress.py`` can map tests to exercises;
2. swaps in the reference solution from ``reference/<same module path>.py`` when asked to by the
   environment variable ``NANOSERVE_REFERENCE``:

   * ``NANOSERVE_REFERENCE=1``    — every exercise uses the reference (see the finished engine);
   * ``NANOSERVE_REFERENCE=auto`` — only exercises you haven't started yet (body is still just
     ``raise TODO(...)``) use the reference; everything you've written runs your code. This is how
     you jump ahead: do M3 first while M1/M2 are filled in by the reference.

Reference solutions live in the ``solutions`` tag (a tag, not a branch, so a plain clone doesn't fetch them):
``git fetch origin tag solutions && git restore --source=tags/solutions -- reference``.
"""
from __future__ import annotations

import ast
import importlib
import inspect
import os
import textwrap
from typing import Any, Callable, TypeVar

T = TypeVar("T")

REGISTRY: dict[str, Any] = {}


def _mode() -> str:
    v = os.environ.get("NANOSERVE_REFERENCE", "").strip().lower()
    if v in ("", "0", "false", "no", "off"):
        return "off"
    return "auto" if v == "auto" else "all"


def reference_mode() -> bool:
    return _mode() != "off"


def _load_reference(obj: Any, eid: str) -> Any:
    mod_name = "reference." + obj.__module__
    try:
        mod = importlib.import_module(mod_name)
    except ModuleNotFoundError as e:
        raise RuntimeError(
            f"NANOSERVE_REFERENCE is set but {mod_name} was not found. Get the reference solutions first: "
            "git fetch origin tag solutions && git restore --source=tags/solutions -- reference"
        ) from e
    try:
        return getattr(mod, obj.__name__)
    except AttributeError as e:
        raise RuntimeError(f"reference for {eid} missing: {mod_name}.{obj.__name__}") from e


def _is_todo_body(body: list[ast.stmt]) -> bool:
    stmts = [s for s in body if not (isinstance(s, ast.Expr) and isinstance(getattr(s, "value", None), ast.Constant))]
    if len(stmts) != 1 or not isinstance(stmts[0], ast.Raise):
        return False
    exc = stmts[0].exc
    func = exc.func if isinstance(exc, ast.Call) else exc
    return isinstance(func, ast.Name) and func.id == "TODO"


def is_unstarted(obj: Any) -> bool:
    """True if ``obj`` is still the untouched stub (every function body is ``raise TODO(...)``)."""
    try:
        tree = ast.parse(textwrap.dedent(inspect.getsource(obj)))
    except (OSError, TypeError, SyntaxError):
        return False
    node = tree.body[0]
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return _is_todo_body(node.body)
    if isinstance(node, ast.ClassDef):
        methods = [n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        return bool(methods) and all(_is_todo_body(m.body) for m in methods)
    return False


def exercise(eid: str) -> Callable[[T], T]:
    """Mark a function or class as exercise ``eid``."""

    def deco(obj: T) -> T:
        mode = _mode()
        use_ref = mode == "all" or (mode == "auto" and is_unstarted(obj))
        target = _load_reference(obj, eid) if use_ref else obj
        REGISTRY[eid] = target
        try:
            setattr(target, "__exercise_id__", eid)
        except (AttributeError, TypeError):
            pass
        return target

    return deco


class TODO(NotImplementedError):
    """Raised by unimplemented exercises. ``tools/progress.py`` reports these as TODO, not FAIL."""
