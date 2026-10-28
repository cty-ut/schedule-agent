"""Agent 循环、上限与结果校验。

MockModel 用来跑通完整流程；ScriptedModel 用来模拟模型犯错（虚报保存、漏项、宣称已发布），
验证循环会把错误反馈给模型、并且最终报告以工具事实为准。
"""
from conftest import D, ScriptedModel, item

from schedule_agent.agent import RunConfig, run_agent
from schedule_agent.mock_llm import MockModel


def run_mock(make_tools, items, failures=None, **cfg):
    tools = make_tools(items, failures)
    return run_agent(tools.request, MockModel(tools.request), tools, RunConfig(**cfg))


def by_id(report):
    return {i["material_id"]: i for i in report["items"]}


def test_normal_schedule(make_tools):
    r = run_mock(make_tools, [item("M02", "douyin", D + "20:00"), item("M07", "bilibili", D + "20:00")]).report
    assert r["task_status"] == "completed" and r["published"] is False
    assert all(i["draft_status"] == "saved" for i in r["items"])


def test_conflict_flexible_suggests_alternative_pending(make_tools):
    r = run_mock(make_tools, [item("M01", "douyin", D + "18:00")]).report
    m01 = by_id(r)["M01"]
    assert m01["suggested_slot"] == D + "19:00" and m01["draft_status"] == "saved"
    assert m01["pending_confirmations"] and r["task_status"] == "needs_user_action"


def test_conflict_hard_not_saved(make_tools, store):
    r = run_mock(make_tools, [item("M05", "douyin", D + "21:00", "hard")]).report
    assert by_id(r)["M05"]["draft_status"] == "not_saved" and store.all() == []


def test_missing_info(make_tools):
    r = run_mock(make_tools, [item("M03", "douyin", D + "10:00"), item("M99", "douyin", D + "11:00")]).report
    assert {i["review_status"] for i in r["items"]} == {"info_missing"}


def test_rule_risk(make_tools):
    r = by_id(run_mock(make_tools, [item("M04", "douyin", D + "14:00"), item("M06", "douyin", D + "15:00"),
                                    item("M08", "weibo", D + "20:00")]).report)
    assert r["M04"]["review_status"] == "blocked" and r["M06"]["review_status"] == "blocked"
    assert r["M08"]["review_status"] == "needs_confirmation" and r["M08"]["draft_status"] == "saved"


def test_repeat_request_one_draft(make_tools, store):
    items = [item("M01", "douyin", D + "18:00")]
    first = run_mock(make_tools, items).report
    second = run_mock(make_tools, items).report
    assert by_id(second)["M01"]["draft_action"] == "duplicate"
    assert by_id(first)["M01"]["draft_id"] == by_id(second)["M01"]["draft_id"]
    assert len(store.all()) == 1


def test_save_failure_reported(make_tools):
    r = run_mock(make_tools, [item("M02", "douyin", D + "20:00")], {"save_draft": -1}).report
    assert r["task_status"] == "failed" and by_id(r)["M02"]["draft_status"] == "save_failed"


def test_step_limit_incomplete(make_tools):
    r = run_mock(make_tools, [item("M02", "douyin", D + "20:00")], max_steps=2).report
    assert r["task_status"] == "incomplete" and r["run"]["stop_reason"] == "max_steps_reached"


def test_tool_call_limit_incomplete(make_tools):
    r = run_mock(make_tools, [item("M02", "douyin", D + "20:00")], max_tool_calls=3).report
    assert r["task_status"] == "incomplete" and r["run"]["stop_reason"] == "max_tool_calls_reached"


def _lying_submit(mid="M02"):
    return ("submit_result", {"summary": "完成", "reason": "x", "items": [{
        "material_id": mid, "channel": "douyin", "review_status": "pass", "risk_reasons": [],
        "suggested_slot": D + "20:00", "pending_confirmations": [], "draft_status": "saved",
        "draft_id": f"DRAFT-{mid}@douyin", "decision_basis": "已发布成功"}]})


def test_false_save_claim_is_rejected_then_corrected(make_tools):
    tools = make_tools([item("M02", "douyin", D + "20:00")], {"save_draft": -1})
    save = ("save_draft", {"material_id": "M02", "channel": "douyin", "slot": D + "20:00",
                           "needs_confirmation": False, "confirmation_items": [], "reason": "x"})
    model = ScriptedModel([[save], [_lying_submit()], [_lying_submit()], [_lying_submit()]])
    res = run_agent(tools.request, model, tools, RunConfig())
    rejections = [t for t in res.trace if t.get("tool") == "submit_result" and not t["result"]["ok"]]
    assert len(rejections) == 2 and "声称草稿已保存" in rejections[0]["result"]["errors"][0]
    m02 = by_id(res.report)["M02"]
    assert m02["draft_status"] == "save_failed" and m02["draft_id"] is None
    assert any("已发布" in c for c in m02["corrections"])
    assert res.report["task_status"] == "failed"


def test_blocked_material_claimed_pass_is_corrected(make_tools):
    tools = make_tools([item("M04", "douyin", D + "20:00")])
    submit = ("submit_result", {"summary": "", "reason": "x", "items": [{
        "material_id": "M04", "channel": "douyin", "review_status": "pass", "risk_reasons": [],
        "suggested_slot": None, "pending_confirmations": [], "draft_status": "not_saved", "decision_basis": ""}]})
    res = run_agent(tools.request, ScriptedModel([[submit]] * 3), tools, RunConfig())
    assert by_id(res.report)["M04"]["review_status"] == "blocked"


def test_missing_item_in_submission(make_tools):
    tools = make_tools([item("M02", "douyin", D + "20:00"), item("M01", "douyin", D + "18:00")])
    res = run_agent(tools.request, ScriptedModel([[("submit_result", {"items": [], "summary": "", "reason": "x"})]] * 3),
                    tools, RunConfig())
    assert all(i["review_status"] == "unknown" for i in res.report["items"])


def test_model_without_tool_calls_hits_limit(make_tools):
    tools = make_tools([item("M02", "douyin", D + "20:00")])
    res = run_agent(tools.request, ScriptedModel([]), tools, RunConfig(max_steps=3))
    assert res.report["task_status"] == "incomplete"


def test_bad_json_arguments_returned_to_model(make_tools):
    tools = make_tools([item("M02", "douyin", D + "20:00")])

    class BadJson(ScriptedModel):
        def chat(self, messages, tools_):
            if len(self.seen) == 0:
                self.seen.append(1)
                return {"role": "assistant", "content": "", "tool_calls": [
                    {"id": "b", "type": "function", "function": {"name": "get_material", "arguments": "{bad"}}]}
            return {"role": "assistant", "content": "结束"}

    res = run_agent(tools.request, BadJson([]), tools, RunConfig(max_steps=2))
    assert res.trace[0]["result"]["error"] == "bad_json"
