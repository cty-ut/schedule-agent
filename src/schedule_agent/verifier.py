"""把模型提交的结论与工具调用的真实结果核对。

模型可能“说错话”：虚报保存成功、漏报素材、把有风险的素材说成通过。
这里以工具账本（ledger）和规则引擎为准：
  - check_submission：submit_result 时调用，发现矛盾就把错误返回给模型，让它修正后重新提交；
  - reconcile：生成最终报告，仍有矛盾时以事实覆盖并记录 corrections。
"""
from __future__ import annotations

from .tools import ToolBox, ToolError

FORBIDDEN_WORDS = ("published", "已发布", "发布成功")


def draft_facts(ledger: list[dict]) -> dict[tuple[str, str], dict]:
    """按 (material_id, channel) 汇总本次运行中 save_draft 的真实结果。"""
    facts: dict[tuple[str, str], dict] = {}
    for rec in ledger:
        if rec["tool"] != "save_draft":
            continue
        key = (rec["args"].get("material_id"), rec["args"].get("channel"))
        res = rec["result"]
        f = facts.setdefault(key, {"status": "not_saved", "attempts": 0, "errors": []})
        f["attempts"] += 1
        if res.get("ok"):
            f.update(status="saved", draft_id=res["draft"]["draft_id"], slot=res["draft"]["slot"],
                     action=res["action"], needs_confirmation=res["draft"]["status"] == "pending_confirmation")
        else:
            f["errors"].append(res.get("error"))
            if f["status"] != "saved" and res.get("error") == "tool_unavailable":
                f["status"] = "save_failed"
    return facts


def _true_review(tools: ToolBox, material_id: str, channel: str) -> dict:
    try:
        return tools.evaluate_rules(material_id, channel, resolve_license=True)
    except ToolError as e:
        return {"review_status": "info_missing", "findings": [{"rule_id": "-", "detail": e.payload["message"]}]}


def _issues(item: dict, req: dict, fact: dict, truth: dict) -> list[str]:
    out = []
    mid = item["material_id"]
    if item.get("draft_status") == "saved" and fact["status"] != "saved":
        out.append(f"{mid}: 声称草稿已保存，但实际保存结果为 {fact['status']}")
    if item.get("draft_status") != "saved" and fact["status"] == "saved":
        out.append(f"{mid}: 草稿实际已保存（{fact['draft_id']}），但结果写成 {item.get('draft_status')}")
    if item.get("draft_status") == "not_saved" and fact["status"] == "save_failed":
        out.append(f"{mid}: 保存调用失败，draft_status 应为 save_failed 而非 not_saved")
    if fact["status"] == "saved" and item.get("suggested_slot") != fact["slot"]:
        out.append(f"{mid}: suggested_slot={item.get('suggested_slot')} 与已保存草稿时段 {fact['slot']} 不一致")
    suggested = item.get("suggested_slot")
    if suggested and req.get("requested_slot") and suggested != req["requested_slot"] and not item.get("pending_confirmations"):
        out.append(f"{mid}: 建议时段与用户要求不同，必须列出待确认项")
    if truth["review_status"] in ("blocked", "info_missing") and item.get("review_status") in ("pass", "needs_confirmation"):
        out.append(f"{mid}: 实际审核结果为 {truth['review_status']}，不能标为 {item.get('review_status')}")
    if truth["review_status"] == "needs_confirmation" and item.get("review_status") == "pass":
        out.append(f"{mid}: 存在须确认风险，review_status 不能为 pass")
    text = " ".join(str(v) for v in item.values())
    if any(w in text for w in FORBIDDEN_WORDS):
        out.append(f"{mid}: 结果中出现“已发布”类表述，本系统只保存草稿")
    return out


def check_submission(submitted: list[dict], tools: ToolBox, ledger: list[dict]) -> list[str]:
    facts = draft_facts(ledger)
    errors = []
    by_key = {(i.get("material_id"), i.get("channel")): i for i in submitted}
    for req in tools.request.get("items", []):
        key = (req.get("material_id"), req.get("channel"))
        item = by_key.get(key)
        if item is None:
            errors.append(f"缺少请求项 {key[0]}@{key[1]} 的结果")
            continue
        fact = facts.get(key, {"status": "not_saved"})
        errors += _issues(item, req, fact, _true_review(tools, *key))
    return errors


def reconcile(submitted: list[dict] | None, tools: ToolBox, ledger: list[dict], finished: bool) -> dict:
    facts = draft_facts(ledger)
    by_key = {(i.get("material_id"), i.get("channel")): i for i in (submitted or [])}
    items = []
    for req in tools.request.get("items", []):
        key = (req.get("material_id"), req.get("channel"))
        fact = facts.get(key, {"status": "not_saved"})
        truth = _true_review(tools, *key)
        model_item = by_key.get(key)
        corrections = _issues(model_item, req, fact, truth) if model_item else []
        item = dict(model_item or {})
        item.setdefault("material_id", key[0])
        item.setdefault("channel", key[1])
        item["requested_slot"] = req.get("requested_slot")
        item["time_requirement"] = req.get("time_requirement", "flexible")
        if model_item is None:
            item.update(review_status="unknown", risk_reasons=[], suggested_slot=None, pending_confirmations=[],
                        decision_basis="模型未给出该项结论（任务未完成）")
            corrections.append(f"{key[0]}: 模型未提交该项结论")
        # 以事实为准覆盖
        item["draft_status"] = fact["status"]
        item["draft_id"] = fact.get("draft_id")
        if fact["status"] == "saved":
            item["suggested_slot"] = fact["slot"]
            item["draft_action"] = fact["action"]
        if fact["status"] == "save_failed":
            item["save_errors"] = fact["errors"]
        if truth["review_status"] in ("blocked", "info_missing") and item.get("review_status") in ("pass", "needs_confirmation"):
            item["review_status"] = truth["review_status"]
            item["risk_reasons"] = [f["detail"] for f in truth["findings"]]
        if truth["review_status"] == "needs_confirmation" and item.get("review_status") == "pass":
            item["review_status"] = "needs_confirmation"
        suggested = item.get("suggested_slot")
        if suggested and req.get("requested_slot") and suggested != req["requested_slot"] and not item.get("pending_confirmations"):
            item["pending_confirmations"] = [f"时段由 {req['requested_slot']} 调整为 {suggested}，需用户确认"]
        item["published"] = False
        item["corrections"] = corrections
        items.append(item)

    if not finished:
        status = "incomplete"
    elif any(i["draft_status"] == "save_failed" for i in items):
        status = "failed"
    elif any(i["review_status"] in ("blocked", "info_missing", "unknown") or i.get("pending_confirmations")
             or i["draft_status"] != "saved" for i in items):
        status = "needs_user_action"
    else:
        status = "completed"
    return {"task_status": status, "items": items, "published": False,
            "notice": "本系统只保存排期草稿，未执行任何发布操作。"}
