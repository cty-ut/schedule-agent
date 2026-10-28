# 02 方案：调用流程、动态决策与技术取舍

## 总体结构

```
请求 JSON ──> agent.run_agent ──(messages + tools)──> 模型（DeepSeek / Mock）
                 │   ▲                                   │ 选择工具 + reason
                 │   └────── 工具结果（JSON）─────────────┘
                 ▼
           tools.ToolBox（业务工具 + 硬约束护栏）──> store.DraftStore（草稿 JSON，幂等）
                 │
     submit_result ──> verifier.check_submission（不一致则打回模型修正）
                 ▼
           verifier.reconcile（以工具事实生成最终报告）──> output.json / trace.md
```

| 模块 | 职责 |
|---|---|
| `src/schedule_agent/agent.py` | ReAct 循环、步数和工具调用上限、提交校验、Trace 记录 |
| `src/schedule_agent/tools.py` | 7 个工具及其 JSON Schema；`save_draft` 内置护栏；故障注入 |
| `src/schedule_agent/store.py` | 草稿存储，按 `(material_id, channel)` 做幂等 |
| `src/schedule_agent/verifier.py` | 核对模型结论与工具事实，纠正虚报 |
| `src/schedule_agent/llm.py` | 兼容 OpenAI 的模型接入（默认 DeepSeek `deepseek-chat`） |
| `src/schedule_agent/mock_llm.py` | 离线固定策略，只验证流程 |

## 工具

| 工具 | 作用 | 模型何时选它 |
|---|---|---|
| `get_material` | 读取素材及缺失字段 | 每项素材的起点 |
| `check_rules` | 规则检查，返回 pass / needs_lookup / needs_confirmation / blocked / info_missing | 素材信息齐全后 |
| `lookup_license` | 补查音乐版权 | `check_rules` 返回 `needs_lookup` |
| `check_slot` | 查询要求时段是否可用 | 审核通过或须确认时 |
| `list_free_slots` | 列出离目标最近的可用时段 | 要求时段被占用 |
| `save_draft` | 保存草稿（幂等） | 决定排期时 |
| `submit_result` | 提交最终结论并结束 | 全部处理完 |

每个工具都有必填参数 `reason`，模型须用一句话说明调用依据。它会写进 Trace 作为"简要决策依据"，不需要模型暴露内部思维过程。

## 动态决策（哪些交给模型）

代码只给出骨架：循环、上限、提交校验。下列决策都由模型根据工具返回的结果决定：

- **补查**：`check_rules` 返回 `needs_lookup` 时，模型自己决定调用 `lookup_license`。补查结果是 `valid` 就继续排期，是 `expired` 就转为阻断（M07 和 M06 两条路径）。
- **替代时段**：`check_slot` 显示被占用时，由模型决定是否调用 `list_free_slots`，以及选哪个时段。
- **请求确认还是阻断**：弹性时间被占用，就保存替代时段并标记待确认；硬性时间被占用，就只给建议、不保存；审核阻断则不排期。
- **失败处理**：`save_draft` 返回 `tool_unavailable` 时，模型决定是否重试（提示词限制最多 1 次），之后如实报告。
- **被护栏拒绝**：如果 `save_draft` 返回 `confirmation_required`、`hard_requirement` 或 `slot_conflict`，模型需要据此调整参数或改为请求确认。
- **被校验器打回**：`submit_result` 返回 `inconsistent_result` 时，模型按错误清单修正后重新提交。

## 关键取舍

1. **护栏放在工具层，而不是只写在提示词里。** 越权改期、为阻断素材排期、缺发布时间时自选时段、保存到冲突时段、改时段却不标待确认，这些都由 `save_draft` 在代码里拒绝。模型就算判断错了，也造不成越权后果，只会拿到一个错误反馈，让它重新决策。
2. **系统里根本没有发布工具。** "不发布"由能力边界保证，不靠模型自觉。
3. **最终报告以事实为准。** 模型提交的结论会和工具账本、规则引擎对账：先打回让模型自己修正（最多 2 次），之后仍不一致的地方由 `reconcile` 用事实覆盖，并把修正写进 `corrections`。这样从机制上保证"不虚报保存成功"。
4. **幂等键是 `(material_id, channel)`，不是请求 ID。** 用户改了时段再提交时，更新原草稿（version+1，保留 history），不另建一份。同一素材在同一渠道始终只有一份草稿，"相同请求只产生一份"自然成立。
5. **同批素材也要互相避让。** 已保存的其他素材草稿在 `check_slot` 里算作占用，避免同一批里排出冲突。
6. **不用框架，原生实现循环。** 需要的只是"工具调用循环 + 上限 + 校验"，原生实现大约 130 行，每个决策点和护栏都看得清楚，也便于测试注入"会犯错的模型"。代价是没有现成的可观测性和断点续跑，这里用自定义 Trace 补上。
7. **两类上限。** `max_steps`（模型轮数，默认 20）和 `max_tool_calls`（默认 40），达到任一上限都返回 `incomplete`，并附上已核实的部分结果。
8. **`temperature=0`。** 尽量降低随机性，方便复现；但真实模型的输出仍可能略有差异。

## 状态定义

- 草稿 `status`：`draft`（与要求一致、无风险）/ `pending_confirmation`（改了时段或有待确认风险）。两者都只是草稿，`published` 恒为 false。
- 任务 `task_status`：`completed`（全部保存、无待确认项）/ `needs_user_action`（存在待确认、阻断或信息缺失）/ `failed`（存在保存失败）/ `incomplete`（达到上限、未正常提交）。
