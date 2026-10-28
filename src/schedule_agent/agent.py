"""ReAct 循环：模型选动作 -> 执行工具 -> 观察结果 -> 模型决定下一步或提交结束。

代码只提供骨架与护栏（步数上限、工具调用上限、提交校验），
具体先查什么、是否补查、选哪个替代时段、是否保存、何时结束，都由模型根据工具结果决定。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from .llm import ChatModel
from .tools import TOOL_SCHEMAS, ToolBox
from .verifier import check_submission, reconcile

SYSTEM_PROMPT = """你是内容团队的“素材审核与发布排期”助手。你的任务：对用户请求中的每一项素材（material_id + channel）
完成审核并给出无冲突、可确认的排期草稿。你只能通过工具获取事实，不得凭空推断。

可用动作由你根据工具结果自行决定，通常包括：读取素材 -> 规则检查 -> (需要时补查版权) -> 查询要求时段
-> (被占用时寻找替代时段) -> 保存草稿；全部处理完后调用 submit_result 结束。

必须遵守的边界：
1. 本系统没有发布能力。只能保存“草稿”，任何输出都不得说已发布/发布成功。
2. time_requirement=hard 的发布时间是硬性要求：被占用时不得自行改期或保存到其他时段，只能给出建议时段并请求用户确认。
3. time_requirement=flexible 且要求时段被占用时，可选择最近的可用时段保存草稿，但必须 needs_confirmation=true 并写明待确认项。
4. 审核为 blocked 或信息缺失（含素材不存在、缺发布时间）时不得排期，说明原因和需要补充的内容。
5. check_rules 返回 needs_lookup 时，先用 lookup_license 补查再下结论。needs_confirmation 风险可以保存草稿，但须标记待确认。
6. 工具返回 tool_unavailable 等可重试错误时，最多重试 1 次；仍失败则如实报告 save_failed，不得声称成功。
7. 每次调用工具都要在 reason 字段里写一句决策依据。
8. submit_result 中每项的 draft_status、draft_id、suggested_slot 必须与 save_draft 的实际返回一致。若 submit_result 返回错误，请按提示修正后重新提交。
"""


@dataclass
class RunConfig:
    max_steps: int = 20          # 模型调用轮数上限
    max_tool_calls: int = 40     # 工具调用总数上限
    max_submit_rejections: int = 2


@dataclass
class RunResult:
    report: dict
    trace: list[dict] = field(default_factory=list)
    messages: list[dict] = field(default_factory=list)


def summarize(tool: str, result: dict) -> str:
    if not result.get("ok", False):
        return f"失败 {result.get('error')}: {result.get('message') or result.get('errors')}"
    if tool == "get_material":
        m = result["material"]
        miss = result["missing_fields"]
        return f"{m['material_id']} 《{m['title']}》 缺失字段={miss or '无'}"
    if tool == "check_rules":
        return "; ".join([result["review_status"]] + [f"{f['rule_id']}:{f['detail']}" for f in result["findings"]])
    if tool == "lookup_license":
        return f"{result['track_id']} -> {result['status']}"
    if tool == "check_slot":
        return f"{result['channel']} {result['slot']} " + ("可用" if result["available"] else f"已占用 by {result['occupied_by']}")
    if tool == "list_free_slots":
        return f"可用时段 {result['free_slots']}"
    if tool == "save_draft":
        d = result["draft"]
        return f"{result['action']} {d['draft_id']} v{d['version']} slot={d['slot']} status={d['status']}"
    if tool == "submit_result":
        return "提交通过"
    return json.dumps(result, ensure_ascii=False)[:200]


def run_agent(request: dict, model: ChatModel, tools: ToolBox, config: RunConfig | None = None) -> RunResult:
    cfg = config or RunConfig()
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "请处理以下排期请求：\n" + json.dumps(request, ensure_ascii=False, indent=2)},
    ]
    trace: list[dict] = []
    ledger: list[dict] = []
    submitted: list[dict] | None = None
    finished = False
    stop_reason = "max_steps_reached"
    rejections = 0
    tool_calls = 0

    for step in range(1, cfg.max_steps + 1):
        reply = model.chat(messages, TOOL_SCHEMAS)
        messages.append(reply)
        calls = reply.get("tool_calls") or []
        if reply.get("content"):
            trace.append({"step": step, "type": "model_text", "content": reply["content"]})
        if not calls:
            # 模型没有调用工具就想结束：提醒它必须通过 submit_result 提交
            messages.append({"role": "user", "content": "请通过工具继续处理，处理完毕后必须调用 submit_result 提交结果。"})
            continue

        for call in calls:
            name = call["function"]["name"]
            try:
                args = json.loads(call["function"]["arguments"] or "{}")
            except json.JSONDecodeError as e:
                args, result = {}, {"ok": False, "error": "bad_json", "message": str(e)}
            else:
                if tool_calls >= cfg.max_tool_calls:
                    result = {"ok": False, "error": "tool_budget_exhausted", "message": "工具调用次数已达上限"}
                elif name == "submit_result":
                    errors = check_submission(args.get("items", []), tools, ledger)
                    if errors and rejections < cfg.max_submit_rejections:
                        rejections += 1
                        result = {"ok": False, "error": "inconsistent_result", "errors": errors}
                    else:
                        submitted = args.get("items", [])
                        finished = True
                        stop_reason = "submitted" if not errors else "submitted_with_corrections"
                        result = {"ok": True}
                else:
                    result = tools.execute(name, args)
                tool_calls += 1
            ledger.append({"tool": name, "args": args, "result": result})
            trace.append({
                "step": step, "type": "tool_call", "tool": name,
                "args": {k: v for k, v in args.items() if k != "reason"},
                "reason": args.get("reason", ""), "result_summary": summarize(name, result), "result": result,
            })
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result, ensure_ascii=False)})

        if finished:
            break
        if tool_calls >= cfg.max_tool_calls:
            stop_reason = "max_tool_calls_reached"
            break

    report = reconcile(submitted, tools, ledger, finished)
    report["run"] = {"model": model.name, "steps": step, "tool_calls": tool_calls, "stop_reason": stop_reason,
                     "limits": {"max_steps": cfg.max_steps, "max_tool_calls": cfg.max_tool_calls}}
    if not finished:
        report["incomplete_reason"] = f"达到上限（{stop_reason}），以下为已核实的部分结果，未处理项需重新运行或人工处理。"
    trace.append({"step": step, "type": "final", "task_status": report["task_status"], "stop_reason": stop_reason})
    return RunResult(report=report, trace=trace, messages=messages)
