# 04_rule_risk — 规则风险：绝对化用语阻断、版权补查过期阻断、促销信息待确认

- 模型: `deepseek-chat`
- 运行选项: `{}`
- 任务状态: **needs_user_action**（stop_reason=submitted，轮数 6，工具调用 12）

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
| 1 | (模型文本) | | I'll start by reading the metadata for all three materials. | |
| 1 | get_material | {"material_id": "M04"} | M04 《全景相机年度盘点》 缺失字段=无 | 读取 M04 元数据以确认必填字段是否齐全 |
| 1 | get_material | {"material_id": "M06"} | M06 《城市夜景延时》 缺失字段=无 | 读取 M06 元数据以确认必填字段是否齐全 |
| 1 | get_material | {"material_id": "M08"} | M08 《双十一预告》 缺失字段=无 | 读取 M08 元数据以确认必填字段是否齐全 |
| 2 | (模型文本) | | Metadata is complete for all three. Now running rule checks per channel. | |
| 2 | check_rules | {"material_id": "M04", "channel": "douyin"} | blocked; R02:含绝对化用语: 全网第一, 100% | M04 拟投抖音，需按渠道规则审核（含绝对化用语风险） |
| 2 | check_rules | {"material_id": "M06", "channel": "douyin"} | needs_lookup; R03:音乐版权待核实，需补查 track_id=TRK-2201 | M06 拟投抖音，音乐版权为待核实，需规则检查 |
| 2 | check_rules | {"material_id": "M08", "channel": "weibo"} | needs_confirmation; R04:含促销信息(折, 限时)，须市场部确认价格口径 | M08 拟投微博，促销类文案需按渠道规则审核 |
| 3 | (模型文本) | | M04 is blocked (no scheduling). M06 needs a license lookup. Let me do that and check slots for M06/M08. | |
| 3 | lookup_license | {"track_id": "TRK-2201"} | TRK-2201 -> expired | check_rules 对 M06 返回 needs_lookup，需补查音乐版权登记状态 |
| 3 | check_slot | {"channel": "douyin", "slot": "2026-11-05 15:00", "material_id": "M06"} | douyin 2026-11-05 15:00 可用 | M06 为 flexible，先确认其要求的 15:00 是否可用 |
| 3 | check_slot | {"channel": "weibo", "slot": "2026-11-05 20:00", "material_id": "M08"} | weibo 2026-11-05 20:00 可用 | M08 为 flexible，先确认其要求的 20:00 是否可用 |
| 4 | (模型文本) | | The license lookup shows TRK-2201 expired on 2026-09-30. Let me re-check M06's rules to get the post-lookup conclusion. | |
| 4 | check_rules | {"channel": "douyin", "material_id": "M06"} | blocked; R03:音乐版权补查结果: expired | 补查结果显示音乐版权已于 2026-09-30 过期，需重新获取规则结论 |
| 5 | (模型文本) | | M06 is now blocked (expired license) — no scheduling. Only M08 can proceed. Saving its draft at the requested 20:00 slot with the promo confirmation flag. | |
| 5 | save_draft | {"material_id": "M08", "channel": "weibo", "slot": "2026-11-05 20:00", "needs_confirmation": true, "confirmation_items": ["促销信息（限时5折）价格口径须市场部确认"]} | created DRAFT-M08@weibo v1 slot=2026-11-05 20:00 status=pending_confirmation | M08 审核为 needs_confirmation 且要求时段 20:00 可用，按原时段保存草稿并标记待确认 |
| 6 | submit_result | (见下方结果) | 提交通过 | 三项素材均已审核并处理完毕，提交最终结果 |
| 6 | (结束) | | needs_user_action / submitted | |

## 最终结果（已与工具事实核对）

| 素材@渠道 | 审核 | 风险原因 | 要求时段 | 建议时段 | 待确认项 | 草稿 | 校验修正 |
|---|---|---|---|---|---|---|---|
| M04@douyin | blocked | ["R02 含绝对化用语：全网第一、100%"] | 2026-11-05 14:00 (flexible) | None | - | not_saved | - |
| M06@douyin | blocked | ["R03 音乐版权补查结果 expired（TRK-2201 于 2026-09-30 到期）"] | 2026-11-05 15:00 (flexible) | None | - | not_saved | - |
| M08@weibo | needs_confirmation | ["R04 含促销信息（折、限时），须市场部确认价格口径"] | 2026-11-05 20:00 (flexible) | 2026-11-05 20:00 | ["促销信息（限时5折）价格口径须市场部确认"] | saved (DRAFT-M08@weibo, created) | - |

> 本系统只保存排期草稿，未执行任何发布操作。
