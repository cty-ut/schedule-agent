# 02_slot_conflict — 时段冲突：弹性时间改替代时段待确认；硬性时间不擅改

- 模型: `mock-policy`
- 运行选项: `{}`
- 任务状态: **needs_user_action**（stop_reason=submitted，轮数 10，工具调用 10）

## 输入

```json
{
  "request_id": "REQ-02",
  "items": [
    {
      "material_id": "M01",
      "channel": "douyin",
      "requested_slot": "2026-11-05 18:00",
      "time_requirement": "flexible"
    },
    {
      "material_id": "M05",
      "channel": "douyin",
      "requested_slot": "2026-11-05 21:00",
      "time_requirement": "hard"
    }
  ]
}
```

## 执行轨迹

| 轮 | 工具 | 参数 | 返回摘要 | 决策依据(reason) |
|---|---|---|---|---|
| 1 | get_material | {"material_id": "M01"} | M01 《秋季新品开箱》 缺失字段=无 | 读取元数据 |
| 2 | check_rules | {"material_id": "M01", "channel": "douyin"} | pass | 执行审核规则 |
| 3 | check_slot | {"channel": "douyin", "slot": "2026-11-05 18:00", "material_id": "M01"} | douyin 2026-11-05 18:00 已占用 by {'type': 'existing_schedule', 'content_id': 'EXT-502', 'owner': '品牌部'} | 查询要求时段 |
| 4 | list_free_slots | {"channel": "douyin", "near_slot": "2026-11-05 18:00", "material_id": "M01"} | 可用时段 ['2026-11-05 19:00', '2026-11-05 17:00', '2026-11-05 20:00'] | 找替代时段 |
| 5 | save_draft | {"material_id": "M01", "channel": "douyin", "slot": "2026-11-05 19:00", "needs_confirmation": true, "confirmation_items": ["2026-11-05 18:00 已占用，建议改为 2026-11-05 19:00，需确认"]} | created DRAFT-M01@douyin v1 slot=2026-11-05 19:00 status=pending_confirmation | 保存草稿 |
| 6 | get_material | {"material_id": "M05"} | M05 《品牌发布会预热》 缺失字段=无 | 读取元数据 |
| 7 | check_rules | {"material_id": "M05", "channel": "douyin"} | pass | 执行审核规则 |
| 8 | check_slot | {"channel": "douyin", "slot": "2026-11-05 21:00", "material_id": "M05"} | douyin 2026-11-05 21:00 已占用 by {'type': 'existing_schedule', 'content_id': 'EXT-503', 'owner': '直播组'} | 查询要求时段 |
| 9 | list_free_slots | {"channel": "douyin", "near_slot": "2026-11-05 21:00", "material_id": "M05"} | 可用时段 ['2026-11-05 22:00', '2026-11-05 20:00', '2026-11-05 17:00'] | 找替代时段 |
| 10 | submit_result | (见下方结果) | 提交通过 | 全部处理完毕 |
| 10 | (结束) | | needs_user_action / submitted | |

## 最终结果（已与工具事实核对）

| 素材@渠道 | 审核 | 风险原因 | 要求时段 | 建议时段 | 待确认项 | 草稿 | 校验修正 |
|---|---|---|---|---|---|---|---|
| M01@douyin | pass | - | 2026-11-05 18:00 (flexible) | 2026-11-05 19:00 | ["2026-11-05 18:00 已占用，建议改为 2026-11-05 19:00，需确认"] | saved (DRAFT-M01@douyin, created) | - |
| M05@douyin | pass | - | 2026-11-05 21:00 (hard) | 2026-11-05 22:00 | ["2026-11-05 21:00 已占用，是否改为 2026-11-05 22:00"] | not_saved | - |

> 本系统只保存排期草稿，未执行任何发布操作。
