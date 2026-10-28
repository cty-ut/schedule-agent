# 10_step_limit — 步数上限：达到上限返回 incomplete

- 模型: `mock-policy`
- 运行选项: `{"max_steps": 3}`
- 任务状态: **incomplete**（stop_reason=max_steps_reached，轮数 3，工具调用 3）

## 输入

```json
{
  "request_id": "REQ-01",
  "items": [
    {
      "material_id": "M02",
      "channel": "douyin",
      "requested_slot": "2026-11-05 20:00",
      "time_requirement": "flexible"
    },
    {
      "material_id": "M07",
      "channel": "bilibili",
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
| 3 | (结束) | | incomplete / max_steps_reached | |

## 最终结果（已与工具事实核对）

| 素材@渠道 | 审核 | 风险原因 | 要求时段 | 建议时段 | 待确认项 | 草稿 | 校验修正 |
|---|---|---|---|---|---|---|---|
| M02@douyin | unknown | - | 2026-11-05 20:00 (flexible) | None | - | not_saved | ["M02: 模型未提交该项结论"] |
| M07@bilibili | unknown | - | 2026-11-05 20:00 (flexible) | None | - | not_saved | ["M07: 模型未提交该项结论"] |

> 本系统只保存排期草稿，未执行任何发布操作。

> 未完成: 达到上限（max_steps_reached），以下为已核实的部分结果，未处理项需重新运行或人工处理。
