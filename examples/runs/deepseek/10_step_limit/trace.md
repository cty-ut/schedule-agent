# 10_step_limit — 步数上限：达到上限返回 incomplete

- 模型: `deepseek-chat`
- 运行选项: `{"max_steps": 3}`
- 任务状态: **incomplete**（stop_reason=max_steps_reached，轮数 3，工具调用 5）

## 输入

```json
{
  "request_id": "REQ-01",
  "items": [
    {
      "material_id": "M02",
      "channel": "douyin",
      "requested_slot": "2026-11-05 20:00",
      "time_requirement": "flexible"
    },
    {
      "material_id": "M07",
      "channel": "bilibili",
      "requested_slot": "2026-11-05 20:00",
      "time_requirement": "flexible"
    }
  ]
}
```

## 执行轨迹

| 轮 | 工具 | 参数 | 返回摘要 | 决策依据(reason) |
|---|---|---|---|---|
| 1 | (模型文本) | | I'll start by reading the metadata for both materials. | |
| 1 | get_material | {"material_id": "M02"} | M02 《运动相机防抖实测》 缺失字段=无 | 读取 M02 元数据以确认必填字段是否齐全 |
| 1 | get_material | {"material_id": "M07"} | M07 《潜水拍摄技巧》 缺失字段=无 | 读取 M07 元数据以确认必填字段是否齐全 |
| 2 | (模型文本) | | Both materials have complete metadata. Now checking rules for each channel. | |
| 2 | check_rules | {"material_id": "M02", "channel": "douyin"} | pass | M02 元数据齐全，按抖音渠道规则审核 |
| 2 | check_rules | {"material_id": "M07", "channel": "bilibili"} | needs_lookup; R03:音乐版权待核实，需补查 track_id=TRK-3105 | M07 元数据齐全但音乐版权待核，按 B 站渠道规则审核 |
| 3 | (模型文本) | | M02 passes. M07 needs a license lookup for TRK-3105. | |
| 3 | lookup_license | {"track_id": "TRK-3105"} | TRK-3105 -> valid | check_rules 对 M07 返回 needs_lookup，需补查音乐版权登记状态 |
| 3 | (结束) | | incomplete / max_steps_reached | |

## 最终结果（已与工具事实核对）

| 素材@渠道 | 审核 | 风险原因 | 要求时段 | 建议时段 | 待确认项 | 草稿 | 校验修正 |
|---|---|---|---|---|---|---|---|
| M02@douyin | unknown | - | 2026-11-05 20:00 (flexible) | None | - | not_saved | ["M02: 模型未提交该项结论"] |
| M07@bilibili | unknown | - | 2026-11-05 20:00 (flexible) | None | - | not_saved | ["M07: 模型未提交该项结论"] |

> 本系统只保存排期草稿，未执行任何发布操作。

> 未完成: 达到上限（max_steps_reached），以下为已核实的部分结果，未处理项需重新运行或人工处理。
