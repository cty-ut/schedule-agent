# 09_save_retry — 保存失败一次后重试成功

- 模型: `deepseek-chat`
- 运行选项: `{"fail": ["save_draft:1"]}`
- 任务状态: **completed**（stop_reason=submitted，轮数 5，工具调用 6）

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
| 1 | (模型文本) | | 我先读取素材元数据，并检查该渠道的审核规则。 | |
| 1 | get_material | {"material_id": "M02"} | M02 《运动相机防抖实测》 缺失字段=无 | 读取 M02 元数据以确认必填字段是否齐全，再决定能否排期 |
| 1 | check_rules | {"material_id": "M02", "channel": "douyin"} | pass | 检查 M02 在抖音渠道的审核风险状态 |
| 2 | (模型文本) | | 审核通过，字段齐全。现在检查请求时段是否可用。 | |
| 2 | check_slot | {"channel": "douyin", "slot": "2026-11-05 20:00", "material_id": "M02"} | douyin 2026-11-05 20:00 可用 | 确认抖音 2026-11-05 20:00 是否被占用，以判断能否按请求时段排期 |
| 3 | (模型文本) | | 请求时段可用，直接保存草稿。 | |
| 3 | save_draft | {"material_id": "M02", "channel": "douyin", "slot": "2026-11-05 20:00", "needs_confirmation": false, "confirmation_items": []} | 失败 tool_unavailable: save_draft 服务暂时不可用（注入故障） | 审核通过、字段齐全且请求时段可用，按用户要求时段保存草稿（不发布） |
| 4 | (模型文本) | | 保存草稿失败，属于可重试错误，按规则重试一次。 | |
| 4 | save_draft | {"channel": "douyin", "confirmation_items": [], "material_id": "M02", "needs_confirmation": false, "slot": "2026-11-05 20:00"} | created DRAFT-M02@douyin v1 slot=2026-11-05 20:00 status=draft | 首次保存遇 tool_unavailable，按规则重试一次保存草稿 |
| 5 | (模型文本) | | 重试成功，草稿已保存。现在提交最终结果。 | |
| 5 | submit_result | (见下方结果) | 提交通过 | 所有素材处理完毕，提交与 save_draft 实际返回一致的最终结果 |
| 5 | (结束) | | completed / submitted | |

## 最终结果（已与工具事实核对）

| 素材@渠道 | 审核 | 风险原因 | 要求时段 | 建议时段 | 待确认项 | 草稿 | 校验修正 |
|---|---|---|---|---|---|---|---|
| M02@douyin | pass | - | 2026-11-05 20:00 (flexible) | 2026-11-05 20:00 | - | saved (DRAFT-M02@douyin, created) | - |

> 本系统只保存排期草稿，未执行任何发布操作。
