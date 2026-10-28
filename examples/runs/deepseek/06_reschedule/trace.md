# 06_reschedule — 更换为已占用时段后重新提交：更新原草稿而非新建

- 模型: `deepseek-chat`
- 运行选项: `{}`
- 任务状态: **needs_user_action**（stop_reason=submitted，轮数 5，工具调用 6）

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
| 1 | (模型文本) | | 我先读取素材元数据，并检查该渠道的审核规则。 | |
| 1 | get_material | {"material_id": "M02"} | M02 《运动相机防抖实测》 缺失字段=无 | 读取 M02 元数据以确认必填字段是否齐全 |
| 1 | check_rules | {"material_id": "M02", "channel": "douyin"} | pass | 检查 M02 在抖音渠道的审核风险 |
| 2 | (模型文本) | | 审核通过，字段齐全。现在检查请求时段是否可用。 | |
| 2 | check_slot | {"channel": "douyin", "slot": "2026-11-05 18:00", "material_id": "M02"} | douyin 2026-11-05 18:00 已占用 by {'type': 'existing_schedule', 'content_id': 'EXT-502', 'owner': '品牌部'} | 确认 M02 请求的抖音 2026-11-05 18:00 时段是否可用 |
| 3 | (模型文本) | | 请求时段已被占用，且该素材为 flexible，因此我查找最近的可用替代时段。 | |
| 3 | list_free_slots | {"channel": "douyin", "near_slot": "2026-11-05 18:00", "material_id": "M02", "limit": 3} | 可用时段 ['2026-11-05 19:00', '2026-11-05 17:00', '2026-11-05 20:00'] | 请求时段被品牌部排期占用，为 flexible 的 M02 寻找最近可用时段 |
| 4 | (模型文本) | | 最近可用时段为 19:00，我保存草稿并标记待确认。 | |
| 4 | save_draft | {"material_id": "M02", "channel": "douyin", "slot": "2026-11-05 19:00", "needs_confirmation": true, "confirmation_items": ["请求时段 2026-11-05 18:00 已被品牌部排期 EXT-502 占用，草稿改排至最近的可用时段 2026-11-05 19:00，请确认是否接受"]} | updated DRAFT-M02@douyin v2 slot=2026-11-05 19:00 status=pending_confirmation | 审核通过且为 flexible，请求时段被占用，按规则保存最近可用时段草稿并标记待确认 |
| 5 | submit_result | (见下方结果) | 提交通过 | 提交 M02 的审核与排期草稿结果 |
| 5 | (结束) | | needs_user_action / submitted | |

## 最终结果（已与工具事实核对）

| 素材@渠道 | 审核 | 风险原因 | 要求时段 | 建议时段 | 待确认项 | 草稿 | 校验修正 |
|---|---|---|---|---|---|---|---|
| M02@douyin | pass | - | 2026-11-05 18:00 (flexible) | 2026-11-05 19:00 | ["请求时段 2026-11-05 18:00 已被品牌部排期 EXT-502 占用，草稿改排至最近的可用时段 2026-11-05 19:00，请确认是否接受"] | saved (DRAFT-M02@douyin, updated) | - |

> 本系统只保存排期草稿，未执行任何发布操作。
