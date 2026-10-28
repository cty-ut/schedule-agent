# 03_missing_info — 素材信息缺失 / 素材不存在 / 缺发布时间

- 模型: `mock-policy`
- 运行选项: `{}`
- 任务状态: **needs_user_action**（stop_reason=submitted，轮数 5，工具调用 5）

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
| 1 | get_material | {"material_id": "M03"} | M03 《》 缺失字段=['title', 'copyright_owner'] | 读取元数据 |
| 2 | get_material | {"material_id": "M99"} | 失败 not_found: 素材 M99 不存在 | 读取元数据 |
| 3 | get_material | {"material_id": "M02"} | M02 《运动相机防抖实测》 缺失字段=无 | 读取元数据 |
| 4 | check_rules | {"material_id": "M02", "channel": "bilibili"} | pass | 执行审核规则 |
| 5 | submit_result | (见下方结果) | 提交通过 | 全部处理完毕 |
| 5 | (结束) | | needs_user_action / submitted | |

## 最终结果（已与工具事实核对）

| 素材@渠道 | 审核 | 风险原因 | 要求时段 | 建议时段 | 待确认项 | 草稿 | 校验修正 |
|---|---|---|---|---|---|---|---|
| M03@douyin | info_missing | ["信息缺失: title, copyright_owner"] | 2026-11-05 10:00 (flexible) | None | ["请补充素材信息后重新提交"] | not_saved | - |
| M99@douyin | info_missing | ["信息缺失: 素材 M99 不存在"] | 2026-11-05 11:00 (flexible) | None | ["请补充素材信息后重新提交"] | not_saved | - |
| M02@bilibili | pass | - | None (flexible) | None | ["请提供发布时间"] | not_saved | - |

> 本系统只保存排期草稿，未执行任何发布操作。
