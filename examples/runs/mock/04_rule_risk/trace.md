# 04_rule_risk — 规则风险：绝对化用语阻断、版权补查过期阻断、促销信息待确认

- 模型: `mock-policy`
- 运行选项: `{}`
- 任务状态: **needs_user_action**（stop_reason=submitted，轮数 10，工具调用 10）

## 输入

```json
{
  "request_id": "REQ-04",
  "items": [
    {
      "material_id": "M04",
      "channel": "douyin",
      "requested_slot": "2026-11-05 14:00",
      "time_requirement": "flexible"
    },
    {
      "material_id": "M06",
      "channel": "douyin",
      "requested_slot": "2026-11-05 15:00",
      "time_requirement": "flexible"
    },
    {
      "material_id": "M08",
      "channel": "weibo",
      "requested_slot": "2026-11-05 20:00",
      "time_requirement": "flexible"
    }
  ]
}
```

## 执行轨迹

| 轮 | 工具 | 参数 | 返回摘要 | 决策依据(reason) |
|---|---|---|---|---|
| 1 | get_material | {"material_id": "M04"} | M04 《全景相机年度盘点》 缺失字段=无 | 读取元数据 |
| 2 | check_rules | {"material_id": "M04", "channel": "douyin"} | blocked; R02:含绝对化用语: 全网第一, 100% | 执行审核规则 |
| 3 | get_material | {"material_id": "M06"} | M06 《城市夜景延时》 缺失字段=无 | 读取元数据 |
| 4 | check_rules | {"material_id": "M06", "channel": "douyin"} | needs_lookup; R03:音乐版权待核实，需补查 track_id=TRK-2201 | 执行审核规则 |
| 5 | lookup_license | {"track_id": "TRK-2201"} | TRK-2201 -> expired | 补查音乐版权 |
| 6 | get_material | {"material_id": "M08"} | M08 《双十一预告》 缺失字段=无 | 读取元数据 |
| 7 | check_rules | {"material_id": "M08", "channel": "weibo"} | needs_confirmation; R04:含促销信息(折, 限时)，须市场部确认价格口径 | 执行审核规则 |
| 8 | check_slot | {"channel": "weibo", "slot": "2026-11-05 20:00", "material_id": "M08"} | weibo 2026-11-05 20:00 可用 | 查询要求时段 |
| 9 | save_draft | {"material_id": "M08", "channel": "weibo", "slot": "2026-11-05 20:00", "needs_confirmation": true, "confirmation_items": ["含促销信息(折, 限时)，须市场部确认价格口径"]} | created DRAFT-M08@weibo v1 slot=2026-11-05 20:00 status=pending_confirmation | 保存草稿 |
| 10 | submit_result | (见下方结果) | 提交通过 | 全部处理完毕 |
| 10 | (结束) | | needs_user_action / submitted | |

## 最终结果（已与工具事实核对）

| 素材@渠道 | 审核 | 风险原因 | 要求时段 | 建议时段 | 待确认项 | 草稿 | 校验修正 |
|---|---|---|---|---|---|---|---|
| M04@douyin | blocked | ["含绝对化用语: 全网第一, 100%"] | 2026-11-05 14:00 (flexible) | None | - | not_saved | - |
| M06@douyin | blocked | ["音乐版权补查结果: expired"] | 2026-11-05 15:00 (flexible) | None | - | not_saved | - |
| M08@weibo | needs_confirmation | ["含促销信息(折, 限时)，须市场部确认价格口径"] | 2026-11-05 20:00 (flexible) | 2026-11-05 20:00 | ["含促销信息(折, 限时)，须市场部确认价格口径"] | saved (DRAFT-M08@weibo, created) | - |

> 本系统只保存排期草稿，未执行任何发布操作。
