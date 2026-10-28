"""离线 Mock 模型：用固定策略代替 LLM 产生工具调用。

边界：它只用于在无 API Key 时验证“循环 / 工具 / 护栏 / 校验 / Trace”这套流程能跑通，
其中的分支是手写规则，**不能证明真实模型的决策能力**。真实决策效果见 examples/runs/deepseek/。
"""
from __future__ import annotations

import json
from typing import Generator

Call = tuple[str, dict]


def _policy(request: dict) -> Generator[Call, dict, None]:
    results = []
    for item in request.get("items", []):
        mid, ch = item.get("material_id"), item.get("channel")
        req_slot, hard = item.get("requested_slot"), item.get("time_requirement") == "hard"
        out = {"material_id": mid, "channel": ch, "review_status": "unknown", "risk_reasons": [],
               "requested_slot": req_slot, "suggested_slot": None, "pending_confirmations": [],
               "draft_status": "not_saved", "draft_id": None, "decision_basis": ""}
        results.append(out)

        r = yield "get_material", {"material_id": mid, "reason": "读取元数据"}
        if not r.get("ok") or r.get("missing_fields"):
            missing = r.get("missing_fields") or [r.get("message", "素材不存在")]
            out.update(review_status="info_missing", risk_reasons=[f"信息缺失: {', '.join(missing)}"],
                       pending_confirmations=["请补充素材信息后重新提交"], decision_basis="素材信息不足，不审核不排期")
            continue

        rules = yield "check_rules", {"material_id": mid, "channel": ch, "reason": "执行审核规则"}
        findings = rules.get("findings", [])
        if rules.get("review_status") == "needs_lookup":
            lic = yield "lookup_license", {"track_id": r["material"].get("music_track_id"), "reason": "补查音乐版权"}
            findings = [f for f in findings if f["rule_id"] != "R03"]
            if lic.get("status") != "valid":
                findings.append({"rule_id": "R03", "severity": "block", "detail": f"音乐版权补查结果: {lic.get('status')}"})
        sev = {f["severity"] for f in findings}
        status = "blocked" if "block" in sev else "needs_confirmation" if "confirm" in sev else "pass"
        out["review_status"] = status
        out["risk_reasons"] = [f["detail"] for f in findings]
        if status == "blocked":
            out["decision_basis"] = "审核阻断，不排期"
            continue
        pending = [f["detail"] for f in findings if f["severity"] == "confirm"]
        if not req_slot:
            out.update(pending_confirmations=pending + ["请提供发布时间"], decision_basis="缺少发布时间，无法排期")
            continue

        s = yield "check_slot", {"channel": ch, "slot": req_slot, "material_id": mid, "reason": "查询要求时段"}
        target = req_slot
        if not s.get("ok"):
            out.update(pending_confirmations=pending + [s.get("message", "时段查询失败")], decision_basis="时段查询失败")
            continue
        if not s["available"]:
            free = yield "list_free_slots", {"channel": ch, "near_slot": req_slot, "material_id": mid, "reason": "找替代时段"}
            alt = (free.get("free_slots") or [None])[0]
            if hard or alt is None:
                out.update(suggested_slot=alt, pending_confirmations=pending + [f"{req_slot} 已占用，是否改为 {alt}"],
                           decision_basis="硬性时间被占用，不擅自改期，请求确认")
                continue
            target = alt
            pending.append(f"{req_slot} 已占用，建议改为 {alt}，需确认")

        args = {"material_id": mid, "channel": ch, "slot": target, "needs_confirmation": bool(pending),
                "confirmation_items": pending, "reason": "保存草稿"}
        saved = yield "save_draft", args
        if not saved.get("ok") and saved.get("retryable"):
            saved = yield "save_draft", {**args, "reason": "保存失败，重试一次"}
        out.update(suggested_slot=target, pending_confirmations=pending)
        if saved.get("ok"):
            out.update(draft_status="saved", draft_id=saved["draft"]["draft_id"], decision_basis="审核通过并保存草稿")
        else:
            out.update(draft_status="save_failed" if saved.get("error") == "tool_unavailable" else "not_saved",
                       decision_basis=f"保存失败: {saved.get('error')}")

    yield "submit_result", {"items": results, "summary": "Mock 策略处理完成", "reason": "全部处理完毕"}


class MockModel:
    name = "mock-policy"

    def __init__(self, request: dict):
        self._gen = _policy(request)
        self._started = False
        self._n = 0

    def chat(self, messages: list[dict], tools: list[dict]) -> dict:
        try:
            if not self._started:
                self._started = True
                name, args = next(self._gen)
            else:
                last = json.loads(messages[-1]["content"]) if messages[-1]["role"] == "tool" else {}
                name, args = self._gen.send(last)
        except StopIteration:
            return {"role": "assistant", "content": "处理结束。"}
        self._n += 1
        return {"role": "assistant", "content": "", "tool_calls": [
            {"id": f"mock-{self._n}", "type": "function",
             "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)}}]}
