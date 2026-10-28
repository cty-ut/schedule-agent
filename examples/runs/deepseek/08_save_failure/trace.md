# 08_save_failure — 保存失败（持续故障）：必须明确返回失败

- 模型: `deepseek-chat`
- 运行选项: `{"fail": ["save_draft"]}`
- 任务状态: **failed**（stop_reason=submitted，轮数 5，工具调用 6）

## 输入

```json
{
  "request_id": "REQ-08",
  "items": [
    {
      "material_id": "M02",
      "channel": "douyin",
      "requested_slot": "2026-11-05 20:00",
      "time_requirement": "flexible"
    }
  ]
}
```

## 执行轨迹

| 轮 | 工具 | 参数 | 返回摘要 | 决策依据(reason) |
|---|---|---|---|---|
| 1 | (模型文本) | | 我先读取素材元数据，并同时做渠道规则检查。 | |
| 1 | get_material | {"material_id": "M02"} | M02 《运动相机防抖实测》 缺失字段=无 | 读取 M02 元数据以确认必填字段是否齐全 |
| 1 | check_rules | {"material_id": "M02", "channel": "douyin"} | pass | 检查 M02 在抖音渠道的审核风险 |
| 2 | (模型文本) | | 审核通过，字段齐全。现在查询请求时段是否可用。 | |
| 2 | check_slot | {"channel": "douyin", "slot": "2026-11-05 20:00", "material_id": "M02"} | douyin 2026-11-05 20:00 可用 | 确认抖音 2026-11-05 20:00 是否可排期 |
| 3 | (模型文本) | | 时段可用，直接保存草稿。 | |
| 3 | save_draft | {"material_id": "M02", "channel": "douyin", "slot": "2026-11-05 20:00", "needs_confirmation": false, "confirmation_items": []} | 失败 tool_unavailable: save_draft 服务暂时不可用（注入故障） | 审核通过且请求时段可用，按用户要求时段保存草稿 |
| 4 | (模型文本) | | 按规则重试一次。 | |
| 4 | save_draft | {"channel": "douyin", "confirmation_items": [], "material_id": "M02", "needs_confirmation": false, "slot": "2026-11-05 20:00"} | 失败 tool_unavailable: save_draft 服务暂时不可用（注入故障） | save_draft 首次返回 tool_unavailable，按规则重试一次 |
| 5 | (模型文本) | | 两次保存均失败，按规则如实报告 save_failed，不声称成功。 | |
| 5 | submit_result | (见下方结果) | 提交通过 | 提交最终处理结果，如实反映保存失败状态 |
| 5 | (结束) | | failed / submitted | |

## 最终结果（已与工具事实核对）

| 素材@渠道 | 审核 | 风险原因 | 要求时段 | 建议时段 | 待确认项 | 草稿 | 校验修正 |
|---|---|---|---|---|---|---|---|
| M02@douyin | pass | - | 2026-11-05 20:00 (flexible) | 2026-11-05 20:00 | - | save_failed | - |

> 本系统只保存排期草稿，未执行任何发布操作。
