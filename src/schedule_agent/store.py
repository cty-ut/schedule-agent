"""排期草稿存储（本地 JSON 文件）。

幂等约定：同一 (material_id, channel) 只有一份草稿。
- 相同时段重复保存 -> 返回已有草稿，不新建（duplicate=True）。
- 不同时段再次保存 -> 原地更新该草稿并递增 version，旧时段随之释放。
草稿只代表“待人工确认的排期”，本模块不存在任何发布动作。
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path


class DraftStore:
    def __init__(self, path: Path | str):
        self.path = Path(path)

    def _load(self) -> dict:
        if not self.path.exists():
            return {"drafts": {}}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    @staticmethod
    def key(material_id: str, channel: str) -> str:
        return f"{material_id}@{channel}"

    def all(self) -> list[dict]:
        return list(self._load()["drafts"].values())

    def get(self, material_id: str, channel: str) -> dict | None:
        return self._load()["drafts"].get(self.key(material_id, channel))

    def holder_of(self, channel: str, slot: str, exclude_material: str | None = None) -> dict | None:
        """返回占用该渠道时段的其他素材草稿（用于批内防冲突）。"""
        for d in self.all():
            if d["channel"] == channel and d["slot"] == slot and d["material_id"] != exclude_material:
                return d
        return None

    def upsert(self, draft: dict) -> tuple[dict, str]:
        """返回 (草稿, 动作)，动作为 created / duplicate / updated。"""
        data = self._load()
        k = self.key(draft["material_id"], draft["channel"])
        now = datetime.now().isoformat(timespec="seconds")
        existing = data["drafts"].get(k)
        if existing and existing["slot"] == draft["slot"]:
            return existing, "duplicate"
        if existing:
            updated = {**existing, **draft, "version": existing["version"] + 1, "updated_at": now}
            updated["history"] = existing.get("history", []) + [{"slot": existing["slot"], "version": existing["version"]}]
            data["drafts"][k] = updated
            self._write(data)
            return updated, "updated"
        created = {**draft, "draft_id": f"DRAFT-{k}", "version": 1, "created_at": now, "updated_at": now, "history": []}
        data["drafts"][k] = created
        self._write(data)
        return created, "created"

    def reset(self) -> None:
        if self.path.exists():
            self.path.unlink()
