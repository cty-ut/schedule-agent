# 01_normal — 正常排期（含版权补查后通过）

- 模型: `mock-policy`
- 运行选项: `{}`
- 任务状态: **completed**（stop_reason=submitted，轮数 10，工具调用 10）

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
| 1 | get_material | {"material_id": "M02"} | M02 《运动相机防抖实测》 缺失字段=无 | 读取元数据 |
| 2 | check_rules | {"material_id": "M02", "channel": "douyin"} | pass | 执行审核规则 |
| 3 | check_slot | {"channel": "douyin", "slot": "2026-11-05 20:00", "material_id": "M02"} | douyin 2026-11-05 20:00 可用 | 查询要求时段 |
| 4 | save_draft | {"material_id": "M02", "channel": "douyin", "slot": "2026-11-05 20:00", "needs_confirmation": false, "confirmation_items": []} | created DRAFT-M02@douyin v1 slot=2026-11-05 20:00 status=draft | 保存草稿 |
| 5 | get_material | {"material_id": "M07"} | M07 《潜水拍摄技巧》 缺失字段=无 | 读取元数据 |
| 6 | check_rules | {"material_id": "M07", "channel": "bilibili"} | needs_lookup; R03:音乐版权待核实，需补查 track_id=TRK-3105 | 执行审核规则 |
| 7 | lookup_license | {"track_id": "TRK-3105"} | TRK-3105 -> valid | 补查音乐版权 |
| 8 | check_slot | {"channel": "bilibili", "slot": "2026-11-05 20:00", "material_id": "M07"} | bilibili 2026-11-05 20:00 可用 | 查询要求时段 |
| 9 | save_draft | {"material_id": "M07", "channel": "bilibili", "slot": "2026-11-05 20:00", "needs_confirmation": false, "confirmation_items": []} | created DRAFT-M07@bilibili v1 slot=2026-11-05 20:00 status=draft | 保存草稿 |
| 10 | submit_result | (见下方结果) | 提交通过 | 全部处理完毕 |
| 10 | (结束) | | completed / submitted | |

## 最终结果（已与工具事实核对）

| 素材@渠道 | 审核 | 风险原因 | 要求时段 | 建议时段 | 待确认项 | 草稿 | 校验修正 |
|---|---|---|---|---|---|---|---|
| M02@douyin | pass | - | 2026-11-05 20:00 (flexible) | 2026-11-05 20:00 | - | saved (DRAFT-M02@douyin, created) | - |
| M07@bilibili | pass | - | 2026-11-05 20:00 (flexible) | 2026-11-05 20:00 | - | saved (DRAFT-M07@bilibili, created) | - |

> 本系统只保存排期草稿，未执行任何发布操作。
