"""加载 data/ 下的合成素材、规则与已有排期。"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data"


@dataclass
class Dataset:
    materials: dict[str, dict]
    rules: list[dict]
    license_registry: dict[str, dict]
    occupied: list[dict]
    channels: list[str]
    publish_hours: tuple[int, int]

    def rule(self, rule_id: str) -> dict:
        return next(r for r in self.rules if r["rule_id"] == rule_id)


def load_dataset(data_dir: Path | str = DEFAULT_DATA_DIR) -> Dataset:
    data_dir = Path(data_dir)

    def read(name: str) -> dict:
        return json.loads((data_dir / name).read_text(encoding="utf-8"))

    materials = read("materials.json")["materials"]
    rules = read("rules.json")
    schedule = read("schedule.json")
    return Dataset(
        materials={m["material_id"]: m for m in materials},
        rules=rules["rules"],
        license_registry=rules["license_registry"],
        occupied=schedule["occupied"],
        channels=schedule["channels"],
        publish_hours=(schedule["publish_hours"]["start"], schedule["publish_hours"]["end"]),
    )
