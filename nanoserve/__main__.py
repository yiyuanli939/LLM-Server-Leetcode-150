"""CLI.

    python -m nanoserve "The scheduler" --max-tokens 60 --stop "."     # M1: one request (= `generate`)
    python -m nanoserve serve --help                                     # M2: continuous-batching server
    python -m nanoserve kv | prefix | compile | config | eval | bench | dashboard | autoscale   # M3–M7
"""
from __future__ import annotations

import argparse
import importlib
import sys

from nanoserve._exercise import reference_mode
from nanoserve.engine import Engine, GenerationConfig
from nanoserve.tokenizer.tokenizer import UnknownCharacterError


SUBCOMMANDS = {
    "serve": ("nanoserve.server.demo", "M2 continuous-batching server on a synthetic trace"),
    "kv": ("nanoserve.kvcache.demo", "M3 paged KV-cache manager under memory pressure"),
    "prefix": ("nanoserve.prefix.demo", "M4 prefix cache + deadline index"),
    "compile": ("nanoserve.ir.demo", "M5 compile & run the model as an operator graph"),
    "config": ("nanoserve.config.demo", "M5 load a server config file"),
    "eval": ("nanoserve.eval.demo", "M6 evaluate outputs / speculative decoding"),
    "bench": ("nanoserve.bench.demo", "M6 benchmark grid & fuzzing"),
    "dashboard": ("nanoserve.dashboard.demo", "M7 text dashboard of a server run"),
    "autoscale": ("nanoserve.autoscale.demo", "M7 capacity planning / autoscaler"),
}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in ("-l", "--list"):
        print("generate (default)  M1 single request")
        for name, (_, desc) in SUBCOMMANDS.items():
            print(f"{name:<19} {desc}")
        return 0
    if argv and argv[0] in SUBCOMMANDS:
        mod_name = SUBCOMMANDS[argv[0]][0]
        try:
            mod = importlib.import_module(mod_name)
            return int(mod.main(argv[1:]) or 0)
        except NotImplementedError as e:
            print(f"还没实现：{e}\n（用 NANOSERVE_REFERENCE=1 可以先看参考实现的效果）", file=sys.stderr)
            return 1
    if argv and argv[0] == "generate":
        argv = argv[1:]
    return generate(argv)


def generate(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="nanoserve", description="nano-serve: a tiny inference engine (`-l` lists subcommands)")
    ap.add_argument("prompt", nargs="*", help="one prompt (several prompts → shared-prefix report)")
    ap.add_argument("--max-tokens", type=int, default=60)
    ap.add_argument("--temperature", type=float, default=0.6)
    ap.add_argument("--top-k", type=int, default=4)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--stop", action="append", default=[], help="stop string (repeatable)")
    ap.add_argument("--no-repeat-window", type=int, default=0)
    ap.add_argument("--width", type=int, default=56, help="width for the justified summary")
    ap.add_argument("--char-stream", action="store_true", help="stream raw characters instead of whole words")
    args = ap.parse_args(argv)

    prompts = args.prompt or ["The scheduler"]
    try:
        engine = Engine()
    except NotImplementedError as e:
        print(f"还没实现：{e}\n先完成 M1 的练习（make m1 查看清单），或用 make demo 看参考实现。", file=sys.stderr)
        return 1

    if len(prompts) > 1:
        shared = engine.shared_prefix(prompts)
        print(f"{len(prompts)} prompts share a prefix of {len(shared)} chars: {shared!r}")
        return 0

    prompt = prompts[0]
    try:
        engine.tokenizer.encode(prompt)
    except UnknownCharacterError as e:
        print(f"[warn] {e}; replacing with spaces", file=sys.stderr)
        prompt = engine.tokenizer.sanitize(prompt)

    cfg = GenerationConfig(
        max_tokens=args.max_tokens, temperature=args.temperature, top_k=args.top_k, seed=args.seed,
        stop=tuple(args.stop), no_repeat_window=args.no_repeat_window, word_stream=not args.char_stream,
    )
    if reference_mode():
        print("[reference mode]", file=sys.stderr)
    print(prompt, end="", flush=True)
    try:
        for chunk in engine.stream(prompt, cfg):
            print(chunk, end="", flush=True)
    except NotImplementedError as e:
        print(f"\n还没实现：{e}", file=sys.stderr)
        return 1
    res = engine.last_result
    print("\n" + "─" * args.width)
    for line in engine.render(prompt + res.text, args.width):
        print(line)
    print("─" * args.width)
    print(f"finish={res.finish_reason} " + " ".join(f"{k}={v}" for k, v in res.stats.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
