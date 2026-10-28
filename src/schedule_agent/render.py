"""把运行记录渲染为便于评审阅读的 Markdown。"""
from __future__ import annotations

import json


def _cell(v) -> str:
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
    return s.replace("|", "\\|").replace("\n", " ")


def render_markdown(title: str, request: dict, report: dict, trace: list[dict], options: dict) -> str:
    lines = [f"# {title}", "", f"- 模型: `{report['run']['model']}`",
             f"- 运行选项: `{json.dumps(options, ensure_ascii=False)}`",
             f"- 任务状态: **{report['task_status']}**（stop_reason={report['run']['stop_reason']}，"
             f"轮数 {report['run']['steps']}，工具调用 {report['run']['tool_calls']}）", "",
             "## 输入", "", "```json", json.dumps(request, ensure_ascii=False, indent=2), "```", "",
             "## 执行轨迹", "", "| 轮 | 工具 | 参数 | 返回摘要 | 决策依据(reason) |", "|---|---|---|---|---|"]
    for t in trace:
        if t["type"] == "tool_call":
            lines.append(f"| {t['step']} | {t['tool']} | {_cell(t['args'] if t['tool'] != 'submit_result' else '(见下方结果)')} "
                         f"| {_cell(t['result_summary'])} | {_cell(t['reason'])} |")
        elif t["type"] == "model_text":
            lines.append(f"| {t['step']} | (模型文本) | | {_cell(t['content'][:300])} | |")
        elif t["type"] == "final":
            lines.append(f"| {t['step']} | (结束) | | {t['task_status']} / {t['stop_reason']} | |")
    lines += ["", "## 最终结果（已与工具事实核对）", "",
              "| 素材@渠道 | 审核 | 风险原因 | 要求时段 | 建议时段 | 待确认项 | 草稿 | 校验修正 |",
              "|---|---|---|---|---|---|---|---|"]
    for i in report["items"]:
        draft = i["draft_status"] + (f" ({i['draft_id']}, {i.get('draft_action')})" if i.get("draft_id") else "")
        lines.append(f"| {i['material_id']}@{i['channel']} | {i['review_status']} | {_cell(i.get('risk_reasons') or '-')} "
                     f"| {i['requested_slot']} ({i['time_requirement']}) | {i.get('suggested_slot')} "
                     f"| {_cell(i.get('pending_confirmations') or '-')} | {draft} | {_cell(i.get('corrections') or '-')} |")
    lines += ["", f"> {report['notice']}"]
    if report.get("incomplete_reason"):
        lines += ["", f"> 未完成: {report['incomplete_reason']}"]
    return "\n".join(lines) + "\n"
