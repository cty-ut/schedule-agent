"""业务工具（本地函数 + 合成数据）及其给模型的 JSON Schema。

设计原则：模型负责“选哪个动作”，工具层负责“硬约束”。
即使模型决策出错，save_draft 也会在代码层拒绝以下操作：
  - 为阻断/信息不足的素材保存草稿；
  - 保存到已被占用的时段；
  - 未经用户同意改动硬性发布时间；
  - 把改时段或有风险的草稿标成无需确认。
系统中不存在发布工具，草稿永远只是“待确认”。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable

from .data import Dataset
from .store import DraftStore

SLOT_FMT = "%Y-%m-%d %H:%M"
SLOT_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:00$")


class ToolError(Exception):
    """可预期的业务错误，以 ok=false 返回给模型。"""

    def __init__(self, code: str, message: str, **extra: Any):
        super().__init__(message)
        self.payload = {"ok": False, "error": code, "message": message, **extra}


@dataclass
class FaultPlan:
    """故障注入：tool_name -> 剩余失败次数（-1 表示一直失败）。"""

    failures: dict[str, int] = field(default_factory=dict)

    def should_fail(self, tool: str) -> bool:
        n = self.failures.get(tool, 0)
        if n == 0:
            return False
        if n > 0:
            self.failures[tool] = n - 1
        return True


def _reason_prop() -> dict:
    return {"type": "string", "description": "一句话说明为什么调用此工具（会写入运行记录）"}


TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "get_material",
            "description": "读取素材元数据。返回 missing_fields 列出为空的必填字段。",
            "parameters": {
                "type": "object",
                "properties": {"material_id": {"type": "string"}, "reason": _reason_prop()},
                "required": ["material_id", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_rules",
            "description": "按审核规则检查素材在指定渠道的风险。review_status: pass / needs_lookup(须补查) / needs_confirmation(可排期但须人工确认) / blocked(阻断) / info_missing(信息不足)。",
            "parameters": {
                "type": "object",
                "properties": {"material_id": {"type": "string"}, "channel": {"type": "string"}, "reason": _reason_prop()},
                "required": ["material_id", "channel", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_license",
            "description": "补查音乐版权登记状态（当 check_rules 返回 needs_lookup 时使用）。补查后 check_rules 会直接反映补查结论，无需重复补查。",
            "parameters": {
                "type": "object",
                "properties": {"track_id": {"type": "string"}, "reason": _reason_prop()},
                "required": ["track_id", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_slot",
            "description": "查询某渠道某时段是否可用（已有排期与本系统草稿都算占用）。slot 格式 'YYYY-MM-DD HH:00'。",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string"},
                    "slot": {"type": "string"},
                    "material_id": {"type": "string", "description": "为哪个素材查询；该素材自己的草稿不算冲突"},
                    "reason": _reason_prop(),
                },
                "required": ["channel", "slot", "material_id", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_free_slots",
            "description": "列出某渠道某天离目标时间最近的可用时段，用于寻找替代时段。",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string"},
                    "near_slot": {"type": "string", "description": "目标时段 'YYYY-MM-DD HH:00'"},
                    "material_id": {"type": "string"},
                    "limit": {"type": "integer", "default": 3},
                    "reason": _reason_prop(),
                },
                "required": ["channel", "near_slot", "material_id", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_draft",
            "description": "保存排期草稿（不会发布）。同一素材+渠道只保留一份草稿：相同时段重复保存返回已有草稿；时段不同则更新。若时段与用户要求不同或存在须确认的风险，needs_confirmation 必须为 true。",
            "parameters": {
                "type": "object",
                "properties": {
                    "material_id": {"type": "string"},
                    "channel": {"type": "string"},
                    "slot": {"type": "string"},
                    "needs_confirmation": {"type": "boolean"},
                    "confirmation_items": {"type": "array", "items": {"type": "string"}, "description": "待用户确认的事项"},
                    "reason": _reason_prop(),
                },
                "required": ["material_id", "channel", "slot", "needs_confirmation", "confirmation_items", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_result",
            "description": "所有素材处理完毕后提交最终结果并结束任务。会与实际工具结果核对，不一致时返回错误要求修正。",
            "parameters": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "material_id": {"type": "string"},
                                "channel": {"type": "string"},
                                "review_status": {"type": "string", "enum": ["pass", "needs_confirmation", "blocked", "info_missing", "unknown"]},
                                "risk_reasons": {"type": "array", "items": {"type": "string"}},
                                "requested_slot": {"type": ["string", "null"]},
                                "suggested_slot": {"type": ["string", "null"]},
                                "pending_confirmations": {"type": "array", "items": {"type": "string"}},
                                "draft_status": {"type": "string", "enum": ["saved", "not_saved", "save_failed"]},
                                "draft_id": {"type": ["string", "null"]},
                                "decision_basis": {"type": "string", "description": "简要决策依据"},
                            },
                            "required": ["material_id", "channel", "review_status", "risk_reasons", "suggested_slot", "pending_confirmations", "draft_status", "decision_basis"],
                        },
                    },
                    "summary": {"type": "string"},
                    "reason": _reason_prop(),
                },
                "required": ["items", "summary", "reason"],
            },
        },
    },
]


def parse_slot(slot: Any) -> datetime:
    if not isinstance(slot, str) or not SLOT_RE.match(slot):
        raise ToolError("invalid_slot", f"时段格式应为 'YYYY-MM-DD HH:00'，收到 {slot!r}")
    return datetime.strptime(slot, SLOT_FMT)


class ToolBox:
    def __init__(self, dataset: Dataset, store: DraftStore, request: dict, faults: FaultPlan | None = None):
        self.ds = dataset
        self.store = store
        self.request = request
        self.faults = faults or FaultPlan()
        self.looked_up: set[str] = set()  # 本次运行已补查过的 track_id，check_rules 据此反映补查结论
        self._handlers: dict[str, Callable[..., dict]] = {
            "get_material": self.get_material,
            "check_rules": self.check_rules,
            "lookup_license": self.lookup_license,
            "check_slot": self.check_slot,
            "list_free_slots": self.list_free_slots,
            "save_draft": self.save_draft,
        }

    # ---- 调度 ----
    def execute(self, name: str, args: dict) -> dict:
        args = {k: v for k, v in args.items() if k != "reason"}
        handler = self._handlers.get(name)
        if handler is None:
            return {"ok": False, "error": "unknown_tool", "message": f"不存在工具 {name}"}
        if self.faults.should_fail(name):
            return {"ok": False, "error": "tool_unavailable", "message": f"{name} 服务暂时不可用（注入故障）", "retryable": True}
        try:
            return handler(**args)
        except ToolError as e:
            return e.payload
        except TypeError as e:
            return {"ok": False, "error": "bad_arguments", "message": str(e)}

    def request_item(self, material_id: str, channel: str) -> dict | None:
        for item in self.request.get("items", []):
            if item.get("material_id") == material_id and item.get("channel") == channel:
                return item
        return None

    # ---- 素材与规则 ----
    def _material(self, material_id: str) -> dict:
        m = self.ds.materials.get(material_id)
        if m is None:
            raise ToolError("not_found", f"素材 {material_id} 不存在")
        return m

    def _missing_fields(self, m: dict) -> list[str]:
        required = self.ds.rule("R01")["required_fields"]
        return [f for f in required if m.get(f) in (None, "")]

    def get_material(self, material_id: str) -> dict:
        m = self._material(material_id)
        return {"ok": True, "material": m, "missing_fields": self._missing_fields(m)}

    def evaluate_rules(self, material_id: str, channel: str, resolve_license: bool = False) -> dict:
        m = self._material(material_id)
        findings: list[dict] = []
        missing = self._missing_fields(m)
        if missing:
            findings.append({"rule_id": "R01", "severity": "block", "detail": f"缺少必填字段: {', '.join(missing)}"})
            return {"review_status": "info_missing", "findings": findings}

        text = f"{m['title']} {m['caption']}"
        hits = [t for t in self.ds.rule("R02")["banned_terms"] if t in text]
        if hits:
            findings.append({"rule_id": "R02", "severity": "block", "detail": f"含绝对化用语: {', '.join(hits)}"})

        lic = m["music_license"]
        if lic == "expired":
            findings.append({"rule_id": "R03", "severity": "block", "detail": "音乐版权已过期"})
        elif lic == "pending_verification":
            if resolve_license or m.get("music_track_id") in self.looked_up:
                reg = self.ds.license_registry.get(m.get("music_track_id", ""), {"status": "not_registered"})
                if reg["status"] != "valid":
                    findings.append({"rule_id": "R03", "severity": "block", "detail": f"音乐版权补查结果: {reg['status']}"})
            else:
                findings.append({"rule_id": "R03", "severity": "lookup", "detail": f"音乐版权待核实，需补查 track_id={m.get('music_track_id')}"})

        promo = [t for t in self.ds.rule("R04")["trigger_terms"] if t in text]
        if promo:
            owner = self.ds.rule("R04")["confirm_owner"]
            findings.append({"rule_id": "R04", "severity": "confirm", "detail": f"含促销信息({', '.join(promo)})，须{owner}确认价格口径"})

        limit = self.ds.rule("R05")["max_duration_sec"].get(channel)
        if limit is None:
            findings.append({"rule_id": "R05", "severity": "block", "detail": f"未知渠道 {channel}"})
        elif m["type"] == "video" and m["duration_sec"] > limit:
            findings.append({"rule_id": "R05", "severity": "block", "detail": f"时长 {m['duration_sec']}s 超过 {channel} 上限 {limit}s"})

        severities = {f["severity"] for f in findings}
        if "block" in severities:
            status = "blocked"
        elif "lookup" in severities:
            status = "needs_lookup"
        elif "confirm" in severities:
            status = "needs_confirmation"
        else:
            status = "pass"
        return {"review_status": status, "findings": findings}

    def check_rules(self, material_id: str, channel: str) -> dict:
        return {"ok": True, "material_id": material_id, "channel": channel, **self.evaluate_rules(material_id, channel)}

    def lookup_license(self, track_id: str) -> dict:
        self.looked_up.add(track_id)
        reg = self.ds.license_registry.get(track_id)
        if reg is None:
            return {"ok": True, "track_id": track_id, "status": "not_registered"}
        return {"ok": True, "track_id": track_id, **reg}

    # ---- 时段 ----
    def _slot_holder(self, channel: str, slot: str, material_id: str | None) -> dict | None:
        for o in self.ds.occupied:
            if o["channel"] == channel and o["slot"] == slot:
                return {"type": "existing_schedule", "content_id": o["content_id"], "owner": o["owner"]}
        d = self.store.holder_of(channel, slot, exclude_material=material_id)
        if d:
            return {"type": "draft", "content_id": d["material_id"], "draft_id": d["draft_id"]}
        return None

    def _validate_slot(self, channel: str, slot: str) -> datetime:
        if channel not in self.ds.channels:
            raise ToolError("unknown_channel", f"未知渠道 {channel}，可选 {self.ds.channels}")
        dt = parse_slot(slot)
        start, end = self.ds.publish_hours
        if not start <= dt.hour <= end:
            raise ToolError("outside_publish_hours", f"可发布时段为 {start:02d}:00-{end:02d}:00")
        return dt

    def check_slot(self, channel: str, slot: str, material_id: str | None = None) -> dict:
        self._validate_slot(channel, slot)
        holder = self._slot_holder(channel, slot, material_id)
        return {"ok": True, "channel": channel, "slot": slot, "available": holder is None, "occupied_by": holder}

    def list_free_slots(self, channel: str, near_slot: str, material_id: str | None = None, limit: int = 3) -> dict:
        target = self._validate_slot(channel, near_slot)
        start, end = self.ds.publish_hours
        day = target.replace(hour=0)
        free = []
        for h in range(start, end + 1):
            s = (day + timedelta(hours=h)).strftime(SLOT_FMT)
            if self._slot_holder(channel, s, material_id) is None:
                free.append((abs(h - target.hour), h < target.hour, s))  # 距离相同时优先晚于目标
        free.sort()
        return {"ok": True, "channel": channel, "near_slot": near_slot, "free_slots": [s for _, _, s in free[: max(1, limit)]]}

    # ---- 草稿 ----
    def save_draft(self, material_id: str, channel: str, slot: str, needs_confirmation: bool,
                   confirmation_items: list[str] | None = None) -> dict:
        confirmation_items = list(confirmation_items or [])
        self._validate_slot(channel, slot)
        item = self.request_item(material_id, channel)
        if item is None:
            raise ToolError("not_in_request", f"{material_id}@{channel} 不在本次请求中，不得保存")

        review = self.evaluate_rules(material_id, channel, resolve_license=True)
        if review["review_status"] in ("blocked", "info_missing"):
            raise ToolError("review_not_passed", "素材审核未通过，不能保存排期草稿",
                            review_status=review["review_status"], findings=review["findings"])

        holder = self._slot_holder(channel, slot, material_id)
        if holder:
            raise ToolError("slot_conflict", f"{channel} {slot} 已被占用", occupied_by=holder)

        requested = item.get("requested_slot")
        if not requested:
            raise ToolError("missing_requested_slot", "用户未提供发布时间，属于信息缺失：不得自行选定时段保存，可给出建议时段并请用户补充")
        slot_changed = slot != requested
        if slot_changed and item.get("time_requirement") == "hard":
            raise ToolError("hard_requirement", f"用户要求的 {requested} 为硬性时间，未经用户同意不得改为 {slot}；请请求确认而不是保存")
        if (slot_changed or review["review_status"] == "needs_confirmation") and not needs_confirmation:
            raise ToolError("confirmation_required", "时段与用户要求不同或存在须确认风险，needs_confirmation 必须为 true")

        draft, action = self.store.upsert({
            "material_id": material_id,
            "channel": channel,
            "slot": slot,
            "requested_slot": requested,
            "status": "pending_confirmation" if needs_confirmation else "draft",
            "confirmation_items": confirmation_items,
            "published": False,
        })
        return {"ok": True, "action": action, "duplicate": action == "duplicate", "draft": draft,
                "note": "仅保存为草稿，未发布"}
