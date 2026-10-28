import json

import pytest

from schedule_agent.data import load_dataset
from schedule_agent.store import DraftStore
from schedule_agent.tools import FaultPlan, ToolBox

D = "2026-11-05 "


def item(mid, ch, slot, req="flexible"):
    return {"material_id": mid, "channel": ch, "requested_slot": slot, "time_requirement": req}


@pytest.fixture
def store(tmp_path):
    return DraftStore(tmp_path / "drafts.json")


@pytest.fixture
def make_tools(store):
    def _make(items, failures=None):
        return ToolBox(load_dataset(), store, {"request_id": "T", "items": items}, FaultPlan(dict(failures or {})))
    return _make


class ScriptedModel:
    """按预设脚本逐轮返回工具调用，用来模拟“行为不当”的模型。"""

    name = "scripted"

    def __init__(self, turns):
        self.turns = list(turns)
        self.seen = []

    def chat(self, messages, tools):
        self.seen.append(messages[-1])
        if not self.turns:
            return {"role": "assistant", "content": "结束"}
        calls = self.turns.pop(0)
        return {"role": "assistant", "content": "", "tool_calls": [
            {"id": f"c{i}", "type": "function", "function": {"name": n, "arguments": json.dumps(a, ensure_ascii=False)}}
            for i, (n, a) in enumerate(calls)]}
