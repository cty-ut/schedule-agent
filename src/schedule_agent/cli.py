"""命令行入口。

  python main.py run --input examples/inputs/01_normal.json [--mock] [--fail save_draft:1]
  python main.py examples [--mock]          # 批量运行 examples/cases.json，写入 examples/runs/<mode>/
  python main.py reset-store
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .agent import RunConfig, run_agent
from .data import load_dataset
from .mock_llm import MockModel
from .render import render_markdown
from .store import DraftStore
from .tools import FaultPlan, ToolBox

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STORE = ROOT / ".runtime" / "drafts.json"


def parse_faults(specs: list[str]) -> FaultPlan:
    """'save_draft' -> 一直失败；'save_draft:1' -> 失败 1 次后恢复。"""
    failures = {}
    for spec in specs or []:
        name, _, n = spec.partition(":")
        failures[name] = int(n) if n else -1
    return FaultPlan(failures)


def make_model(mock: bool, request: dict):
    if mock:
        return MockModel(request)
    from .llm import OpenAICompatibleModel
    return OpenAICompatibleModel()


def execute(request: dict, *, mock: bool, store: DraftStore, faults: list[str], max_steps: int, max_tool_calls: int):
    tools = ToolBox(load_dataset(), store, request, parse_faults(faults))
    return run_agent(request, make_model(mock, request), tools, RunConfig(max_steps=max_steps, max_tool_calls=max_tool_calls))


def write_run(out_dir: Path, title: str, request: dict, result, options: dict, store: DraftStore) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "output.json").write_text(json.dumps(result.report, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "trace.json").write_text(json.dumps(result.trace, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "drafts_after.json").write_text(json.dumps(store.all(), ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "trace.md").write_text(render_markdown(title, request, result.report, result.trace, options), encoding="utf-8")


def cmd_run(a) -> int:
    request = json.loads(Path(a.input).read_text(encoding="utf-8"))
    store = DraftStore(a.store)
    if a.reset_store:
        store.reset()
    result = execute(request, mock=a.mock, store=store, faults=a.fail, max_steps=a.max_steps, max_tool_calls=a.max_tool_calls)
    print(render_markdown(Path(a.input).stem, request, result.report, result.trace,
                          {"mock": a.mock, "fail": a.fail, "max_steps": a.max_steps}))
    if a.out:
        write_run(Path(a.out), Path(a.input).stem, request, result, {"mock": a.mock, "fail": a.fail}, store)
    return 0


def cmd_examples(a) -> int:
    cases = json.loads((ROOT / "examples" / "cases.json").read_text(encoding="utf-8"))
    mode = "mock" if a.mock else "deepseek"
    for case in cases:
        if a.only and case["name"] not in a.only:
            continue
        request = json.loads((ROOT / case["input"]).read_text(encoding="utf-8"))
        store = DraftStore(ROOT / ".runtime" / mode / f"{case['name']}.json")
        store.reset()
        for pre in case.get("pre_drafts", []):  # 预置“上一次运行”留下的草稿
            store.upsert(pre)
        opts = case.get("options", {})
        for run_i in range(1, case.get("repeat", 1) + 1):
            result = execute(request, mock=a.mock, store=store, faults=opts.get("fail", []),
                             max_steps=opts.get("max_steps", 20), max_tool_calls=opts.get("max_tool_calls", 40))
            suffix = f"run{run_i}" if case.get("repeat", 1) > 1 else ""
            out = ROOT / "examples" / "runs" / mode / case["name"] / suffix
            title = f"{case['name']} {suffix}".strip() + f" — {case['description']}"
            write_run(out, title, request, result, opts, store)
            print(f"[{mode}] {case['name']} run{run_i}: {result.report['task_status']}")
    write_summary(ROOT / "examples" / "runs" / mode)
    return 0


def write_summary(runs_dir: Path) -> None:
    """从各用例目录的 output.json 汇总，--only 重跑单个用例时其余结果保持不变。"""
    summary = []
    for out in sorted(runs_dir.glob("*/**/output.json")):
        r = json.loads(out.read_text(encoding="utf-8"))
        drafts = json.loads((out.parent / "drafts_after.json").read_text(encoding="utf-8"))
        summary.append({"run": out.parent.relative_to(runs_dir).as_posix(), "task_status": r["task_status"],
                        "stop_reason": r["run"]["stop_reason"], "steps": r["run"]["steps"], "tool_calls": r["run"]["tool_calls"],
                        "drafts_in_store": len(drafts),
                        "items": {f"{i['material_id']}@{i['channel']}": [i["review_status"], i.get("suggested_slot"),
                                                                         i["draft_status"], i.get("draft_action")]
                                  for i in r["items"]}})
    runs_dir.mkdir(parents=True, exist_ok=True)
    (runs_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    p = argparse.ArgumentParser(prog="schedule-agent", description="素材审核与发布排期 Agent")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="处理单个请求")
    r.add_argument("--input", required=True)
    r.add_argument("--mock", action="store_true", help="离线 Mock 策略（只验证流程，不代表模型决策）")
    r.add_argument("--fail", action="append", default=[], help="故障注入，如 save_draft 或 save_draft:1")
    r.add_argument("--max-steps", type=int, default=20)
    r.add_argument("--max-tool-calls", type=int, default=40)
    r.add_argument("--store", default=str(DEFAULT_STORE))
    r.add_argument("--reset-store", action="store_true")
    r.add_argument("--out", help="把 output/trace 写入该目录")
    r.set_defaults(fn=cmd_run)

    e = sub.add_parser("examples", help="批量运行 examples/cases.json")
    e.add_argument("--mock", action="store_true")
    e.add_argument("--only", nargs="*", help="只运行指定用例名")
    e.set_defaults(fn=cmd_examples)

    s = sub.add_parser("reset-store", help="清空默认草稿库")
    s.add_argument("--store", default=str(DEFAULT_STORE))
    s.set_defaults(fn=lambda a: (DraftStore(a.store).reset(), print("已清空", a.store), 0)[-1])

    a = p.parse_args(argv)
    if getattr(a, "max_steps", 1) < 1:
        p.error("--max-steps 至少为 1")
    return a.fn(a)
