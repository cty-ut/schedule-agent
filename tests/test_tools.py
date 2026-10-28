"""工具层与护栏：不依赖模型，直接验证硬约束。"""
from conftest import D, item

from schedule_agent.tools import TOOL_SCHEMAS


def save(tools, mid, ch, slot, confirm=False, items=None):
    return tools.execute("save_draft", {"material_id": mid, "channel": ch, "slot": slot,
                                        "needs_confirmation": confirm, "confirmation_items": items or []})


def test_no_publish_capability():
    names = {s["function"]["name"] for s in TOOL_SCHEMAS}
    assert not any("publish" in n for n in names)


def test_slot_occupied_and_nearest_alternative(make_tools):
    t = make_tools([item("M01", "douyin", D + "18:00")])
    r = t.execute("check_slot", {"channel": "douyin", "slot": D + "18:00", "material_id": "M01"})
    assert r["available"] is False and r["occupied_by"]["content_id"] == "EXT-502"
    free = t.execute("list_free_slots", {"channel": "douyin", "near_slot": D + "18:00", "material_id": "M01"})
    assert free["free_slots"][0] == D + "19:00"


def test_invalid_slot_and_channel(make_tools):
    t = make_tools([])
    assert t.execute("check_slot", {"channel": "douyin", "slot": "明天晚上"})["error"] == "invalid_slot"
    assert t.execute("check_slot", {"channel": "douyin", "slot": D + "23:00"})["error"] == "outside_publish_hours"
    assert t.execute("check_slot", {"channel": "tiktok", "slot": D + "20:00"})["error"] == "unknown_channel"


def test_rules_statuses(make_tools):
    t = make_tools([])
    status = lambda mid, ch="douyin": t.execute("check_rules", {"material_id": mid, "channel": ch})
    assert status("M01")["review_status"] == "pass"
    assert status("M03")["review_status"] == "info_missing"
    assert status("M04")["review_status"] == "blocked"
    assert status("M06")["review_status"] == "needs_lookup"
    assert status("M08", "weibo")["review_status"] == "needs_confirmation"
    assert status("M99")["error"] == "not_found"
    assert t.execute("lookup_license", {"track_id": "TRK-2201"})["status"] == "expired"


def test_check_rules_reflects_license_lookup(make_tools):
    t = make_tools([])
    rules = lambda mid: t.execute("check_rules", {"material_id": mid, "channel": "douyin"})["review_status"]
    assert rules("M06") == "needs_lookup" and rules("M07") == "needs_lookup"
    t.execute("lookup_license", {"track_id": "TRK-2201"})
    t.execute("lookup_license", {"track_id": "TRK-3105"})
    assert rules("M06") == "blocked" and rules("M07") == "pass"


def test_duplicate_save_creates_one_draft(make_tools, store):
    t = make_tools([item("M02", "douyin", D + "20:00")])
    first, second = save(t, "M02", "douyin", D + "20:00"), save(t, "M02", "douyin", D + "20:00")
    assert first["action"] == "created" and second["action"] == "duplicate"
    assert first["draft"]["draft_id"] == second["draft"]["draft_id"]
    assert len(store.all()) == 1


def test_resubmit_with_new_slot_updates_same_draft(make_tools, store):
    t = make_tools([item("M02", "douyin", D + "20:00")])
    save(t, "M02", "douyin", D + "20:00")
    t2 = make_tools([item("M02", "douyin", D + "18:00")])  # 用户改成已占用时段后重新提交
    r = save(t2, "M02", "douyin", D + "19:00", confirm=True, items=["18:00 已占用"])
    assert r["action"] == "updated" and r["draft"]["version"] == 2
    assert len(store.all()) == 1 and store.all()[0]["history"][0]["slot"] == D + "20:00"


def test_guard_rejects_occupied_slot(make_tools):
    t = make_tools([item("M01", "douyin", D + "18:00")])
    assert save(t, "M01", "douyin", D + "18:00")["error"] == "slot_conflict"


def test_guard_other_material_draft_counts_as_occupied(make_tools):
    t = make_tools([item("M02", "douyin", D + "20:00"), item("M07", "douyin", D + "20:00")])
    assert save(t, "M02", "douyin", D + "20:00")["ok"]
    assert t.execute("check_slot", {"channel": "douyin", "slot": D + "20:00", "material_id": "M07"})["available"] is False
    assert save(t, "M07", "douyin", D + "20:00")["error"] == "slot_conflict"


def test_guard_changed_slot_requires_confirmation(make_tools):
    t = make_tools([item("M01", "douyin", D + "18:00")])
    assert save(t, "M01", "douyin", D + "19:00", confirm=False)["error"] == "confirmation_required"
    ok = save(t, "M01", "douyin", D + "19:00", confirm=True, items=["改期需确认"])
    assert ok["ok"] and ok["draft"]["status"] == "pending_confirmation" and ok["draft"]["published"] is False


def test_guard_hard_requirement_cannot_be_changed(make_tools, store):
    t = make_tools([item("M05", "douyin", D + "21:00", "hard")])
    assert save(t, "M05", "douyin", D + "22:00", confirm=True)["error"] == "hard_requirement"
    assert store.all() == []


def test_guard_blocked_and_missing_cannot_be_saved(make_tools, store):
    t = make_tools([item("M04", "douyin", D + "14:00"), item("M03", "douyin", D + "10:00"), item("M06", "douyin", D + "15:00")])
    assert save(t, "M04", "douyin", D + "14:00")["error"] == "review_not_passed"
    assert save(t, "M03", "douyin", D + "10:00")["error"] == "review_not_passed"
    assert save(t, "M06", "douyin", D + "15:00")["error"] == "review_not_passed"  # 跳过补查也拦得住
    assert store.all() == []


def test_guard_missing_requested_slot(make_tools, store):
    # 真实模型曾在缺发布时间时自选 10:00 保存草稿（见 examples/runs/deepseek_before_fix/03_missing_info）
    t = make_tools([item("M02", "bilibili", None)])
    assert save(t, "M02", "bilibili", D + "10:00", confirm=True, items=["请确认时间"])["error"] == "missing_requested_slot"
    assert store.all() == []


def test_guard_risk_needs_confirmation(make_tools):
    t = make_tools([item("M08", "weibo", D + "20:00")])
    assert save(t, "M08", "weibo", D + "20:00", confirm=False)["error"] == "confirmation_required"


def test_guard_not_in_request(make_tools):
    t = make_tools([item("M02", "douyin", D + "20:00")])
    assert save(t, "M01", "douyin", D + "20:00")["error"] == "not_in_request"


def test_fault_injection_once_then_recover(make_tools, store):
    t = make_tools([item("M02", "douyin", D + "20:00")], {"save_draft": 1})
    assert save(t, "M02", "douyin", D + "20:00")["error"] == "tool_unavailable"
    assert save(t, "M02", "douyin", D + "20:00")["ok"]
    assert len(store.all()) == 1


def test_fault_injection_always(make_tools, store):
    t = make_tools([item("M02", "douyin", D + "20:00")], {"save_draft": -1})
    for _ in range(3):
        assert save(t, "M02", "douyin", D + "20:00")["ok"] is False
    assert store.all() == []
