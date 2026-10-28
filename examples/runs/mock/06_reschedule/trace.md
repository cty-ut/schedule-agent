# 06_reschedule — 更换为已占用时段后重新提交：更新原草稿而非新建

- 模型: `mock-policy`
- 运行选项: `{}`
- 任务状态: **needs_user_action**（stop_reason=submitted，轮数 6，工具调用 6）

## 输入

```json
{
  "request_id": "REQ-06",
  "items": [
    {
      "material_id": "M02",
      "channel": "douyin",
      "requested_slot": "2026-11-05 18:00",
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
| 3 | check_slot | {"channel": "douyin", "slot": "2026-11-05 18:00", "material_id": "M02"} | douyin 2026-11-05 18:00 已占用 by {'type': 'existing_schedule', 'content_id': 'EXT-502', 'owner': '品牌部'} | 查询要求时段 |
| 4 | list_free_slots | {"channel": "douyin", "near_slot": "2026-11-05 18:00", "material_id": "M02"} | 可用时段 ['2026-11-05 19:00', '2026-11-05 17:00', '2026-11-05 20:00'] | 找替代时段 |
| 5 | save_draft | {"material_id": "M02", "channel": "douyin", "slot": "2026-11-05 19:00", "needs_confirmation": true, "confirmation_items": ["2026-11-05 18:00 已占用，建议改为 2026-11-05 19:00，需确认"]} | updated DRAFT-M02@douyin v2 slot=2026-11-05 19:00 status=pending_confirmation | 保存草稿 |
| 6 | submit_result | (见下方结果) | 提交通过 | 全部处理完毕 |
| 6 | (结束) | | needs_user_action / submitted | |

## 最终结果（已与工具事实核对）

| 素材@渠道 | 审核 | 风险原因 | 要求时段 | 建议时段 | 待确认项 | 草稿 | 校验修正 |
|---|---|---|---|---|---|---|---|
| M02@douyin | pass | - | 2026-11-05 18:00 (flexible) | 2026-11-05 19:00 | ["2026-11-05 18:00 已占用，建议改为 2026-11-05 19:00，需确认"] | saved (DRAFT-M02@douyin, updated) | - |

> 本系统只保存排期草稿，未执行任何发布操作。
