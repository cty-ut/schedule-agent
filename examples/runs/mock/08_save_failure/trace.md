# 08_save_failure — 保存失败（持续故障）：必须明确返回失败

- 模型: `mock-policy`
- 运行选项: `{"fail": ["save_draft"]}`
- 任务状态: **failed**（stop_reason=submitted，轮数 6，工具调用 6）

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
| 1 | get_material | {"material_id": "M02"} | M02 《运动相机防抖实测》 缺失字段=无 | 读取元数据 |
| 2 | check_rules | {"material_id": "M02", "channel": "douyin"} | pass | 执行审核规则 |
| 3 | check_slot | {"channel": "douyin", "slot": "2026-11-05 20:00", "material_id": "M02"} | douyin 2026-11-05 20:00 可用 | 查询要求时段 |
| 4 | save_draft | {"material_id": "M02", "channel": "douyin", "slot": "2026-11-05 20:00", "needs_confirmation": false, "confirmation_items": []} | 失败 tool_unavailable: save_draft 服务暂时不可用（注入故障） | 保存草稿 |
| 5 | save_draft | {"material_id": "M02", "channel": "douyin", "slot": "2026-11-05 20:00", "needs_confirmation": false, "confirmation_items": []} | 失败 tool_unavailable: save_draft 服务暂时不可用（注入故障） | 保存失败，重试一次 |
| 6 | submit_result | (见下方结果) | 提交通过 | 全部处理完毕 |
| 6 | (结束) | | failed / submitted | |

## 最终结果（已与工具事实核对）

| 素材@渠道 | 审核 | 风险原因 | 要求时段 | 建议时段 | 待确认项 | 草稿 | 校验修正 |
|---|---|---|---|---|---|---|---|
| M02@douyin | pass | - | 2026-11-05 20:00 (flexible) | 2026-11-05 20:00 | - | save_failed | - |

> 本系统只保存排期草稿，未执行任何发布操作。
