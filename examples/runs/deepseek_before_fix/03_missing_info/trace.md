# 03_missing_info — 素材信息缺失 / 素材不存在 / 缺发布时间

- 模型: `deepseek-chat`
- 运行选项: `{}`
- 任务状态: **needs_user_action**（stop_reason=submitted，轮数 5，工具调用 8）

## 输入

```json
{
  "request_id": "REQ-03",
  "items": [
    {
      "material_id": "M03",
      "channel": "douyin",
      "requested_slot": "2026-11-05 10:00",
      "time_requirement": "flexible"
    },
    {
      "material_id": "M99",
      "channel": "douyin",
      "requested_slot": "2026-11-05 11:00",
      "time_requirement": "flexible"
    },
    {
      "material_id": "M02",
      "channel": "bilibili",
      "requested_slot": null,
      "time_requirement": "flexible"
    }
  ]
}
```

## 执行轨迹

| 轮 | 工具 | 参数 | 返回摘要 | 决策依据(reason) |
|---|---|---|---|---|
| 1 | (模型文本) | | I'll start by reading the metadata for all three materials. | |
| 1 | get_material | {"material_id": "M03"} | M03 《》 缺失字段=['title', 'copyright_owner'] | 读取 M03 元数据以确认必填字段是否齐全 |
| 1 | get_material | {"material_id": "M99"} | 失败 not_found: 素材 M99 不存在 | 读取 M99 元数据以确认素材是否存在及字段是否齐全 |
| 1 | get_material | {"material_id": "M02"} | M02 《运动相机防抖实测》 缺失字段=无 | 读取 M02 元数据以确认必填字段是否齐全 |
| 2 | (模型文本) | | M03 缺少必填字段（title、copyright_owner），M99 不存在，M02 完整。接下来我会对 M03 和 M02 运行规则检查。 | |
| 2 | check_rules | {"material_id": "M03", "channel": "douyin"} | info_missing; R01:缺少必填字段: title, copyright_owner | M03 拟投抖音，需先做渠道审核规则检查 |
| 2 | check_rules | {"material_id": "M02", "channel": "bilibili"} | pass | M02 拟投 B 站，需先做渠道审核规则检查 |
| 3 | (模型文本) | | M03 因缺少必填字段被阻断，M02 通过。M02 没有请求时段，因此我需要为它找一个可用时段。 | |
| 3 | list_free_slots | {"channel": "bilibili", "near_slot": "2026-11-05 10:00", "material_id": "M02", "limit": 3} | 可用时段 ['2026-11-05 10:00', '2026-11-05 11:00', '2026-11-05 09:00'] | M02 未指定发布时间，需查询 B 站近期可用时段以给出建议排期 |
| 4 | (模型文本) | | M02 在 B 站 2026-11-05 10:00 可用。我会保存该草稿。 | |
| 4 | save_draft | {"material_id": "M02", "channel": "bilibili", "slot": "2026-11-05 10:00", "needs_confirmation": true, "confirmation_items": ["用户未指定发布时间，建议时段 2026-11-05 10:00 需用户确认"]} | created DRAFT-M02@bilibili v1 slot=2026-11-05 10:00 status=pending_confirmation | M02 审核通过且该时段可用，但用户未指定时间，故保存草稿并标记待确认 |
| 5 | submit_result | (见下方结果) | 提交通过 | 三项素材均已处理完毕，提交最终结果 |
| 5 | (结束) | | needs_user_action / submitted | |

## 最终结果（已与工具事实核对）

| 素材@渠道 | 审核 | 风险原因 | 要求时段 | 建议时段 | 待确认项 | 草稿 | 校验修正 |
|---|---|---|---|---|---|---|---|
| M03@douyin | info_missing | ["缺少必填字段: title, copyright_owner（规则 R01，阻断级）"] | 2026-11-05 10:00 (flexible) | None | ["需补充素材标题 title", "需补充版权方 copyright_owner"] | not_saved | - |
| M99@douyin | info_missing | ["素材 M99 不存在（not_found）"] | 2026-11-05 11:00 (flexible) | None | ["请确认正确的素材 ID 或先上传该素材"] | not_saved | - |
| M02@bilibili | pass | - | None (flexible) | 2026-11-05 10:00 | ["用户未指定发布时间，建议时段 2026-11-05 10:00 需用户确认"] | saved (DRAFT-M02@bilibili, created) | - |

> 本系统只保存排期草稿，未执行任何发布操作。
