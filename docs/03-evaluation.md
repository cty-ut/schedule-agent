# 03 评估：测试预期、实际结果、失败与限制

## 验证方式

| 层次 | 内容 | 命令 | 结果 |
|---|---|---|---|
| 单元 / 护栏 | 工具层硬约束、幂等、故障注入（不依赖模型） | `python -m pytest -q tests/test_tools.py` | 通过 |
| Agent 循环 | Mock 端到端；用"会犯错的脚本模型"测虚报保存、漏项、宣称已发布、上限、坏 JSON | `python -m pytest -q tests/test_agent.py` | 通过 |
| 合计 | | `python -m pytest -q` | **31 passed** |
| 真实模型 | DeepSeek `deepseek-chat`，`temperature=0`，10 个用例 / 11 次运行 | `python main.py examples` | 见下表，[summary.json](../examples/runs/deepseek/summary.json) |
| 离线流程 | 同一批用例使用 Mock 策略 | `python main.py examples --mock` | [examples/runs/mock/](../examples/runs/mock/) |

每个用例目录下都有：`trace.md`（便于阅读的执行轨迹）、`trace.json`（完整的参数与返回）、`output.json`（最终结果）、`drafts_after.json`（运行后草稿库的实际内容，用来核对"只有一份草稿"和"保存失败时库里为空"）。

## 用例与验收点对照（真实模型 DeepSeek 结果）

| 用例 | 覆盖验收点 | 预期 | 实际 | 记录 |
|---|---|---|---|---|
| 01_normal | 正常排期 | M02、M07 均保存草稿；M07 版权先补查 | `completed`；M07 经 `lookup_license → valid` 后保存，两份草稿 | [trace](../examples/runs/deepseek/01_normal/trace.md) |
| 02_slot_conflict | 时段冲突 | M01（弹性）18:00 被占，改 19:00 并待确认；M05（硬性）21:00 被占，不改不存，请求确认 | 与预期一致。M01 保存为 `pending_confirmation`；M05 `not_saved`，建议 22:00，备选 20:00、19:00 | [trace](../examples/runs/deepseek/02_slot_conflict/trace.md) |
| 03_missing_info | 素材信息缺失 | M03 缺字段、M99 不存在、M02 缺发布时间，三者均不排期 | 三项均 `not_saved`；M02 只给建议时段（过程见下方"路径 C"） | [trace](../examples/runs/deepseek/03_missing_info/trace.md) |
| 04_rule_risk | 规则风险 | M04 绝对化用语阻断；M06 补查后版权过期阻断；M08 促销信息可存草稿但待市场部确认 | 与预期一致 | [trace](../examples/runs/deepseek/04_rule_risk/trace.md) |
| 05_duplicate | 重复提交 | 同一请求跑两次，草稿库始终只有 1 份 | run1 `created`，run2 `duplicate`，同一 `draft_id`，库内 1 份 | [run1](../examples/runs/deepseek/05_duplicate/run1/trace.md) / [run2](../examples/runs/deepseek/05_duplicate/run2/trace.md) / [drafts](../examples/runs/deepseek/05_duplicate/run2/drafts_after.json) |
| 06_reschedule | 重复提交 + 冲突（改成已占用时段再提交） | 已有 M02@20:00 草稿；改为请求 18:00（已占用）后，更新原草稿到 19:00，不新建 | `updated`，version 2，history 保留 20:00，库内 1 份 | [trace](../examples/runs/deepseek/06_reschedule/trace.md) / [drafts](../examples/runs/deepseek/06_reschedule/drafts_after.json) |
| 07_batch_conflict | 时段冲突（同批内） | M02、M07 都要 20:00，后保存的一项须改期 | M07 保存时被护栏以 `slot_conflict` 拒绝，模型改选 19:00 并标记待确认 | [trace](../examples/runs/deepseek/07_batch_conflict/trace.md) |
| 08_save_failure | 保存失败 | 持续失败，须明确报告 `save_failed`，不得称成功 | 模型重试 1 次后停止，如实报告；任务 `failed`；草稿库为空 | [trace](../examples/runs/deepseek/08_save_failure/trace.md) |
| 09_save_retry | 保存失败（可恢复） | 失败 1 次后重试成功 | 重试成功，`completed` | [trace](../examples/runs/deepseek/09_save_retry/trace.md) |
| 10_step_limit | 步数上限 | `max_steps=3`，返回明确的未完成状态 | `incomplete / max_steps_reached`，未提交项标记为 `unknown` | [trace](../examples/runs/deepseek/10_step_limit/trace.md) |

全部 11 次运行里，`corrections`（校验器的事后修正）为空，只有 10_step_limit 例外：那一次模型来不及提交，按设计由校验器补上 `unknown`。也就是说，真实模型提交的结论与工具事实一致，没有出现虚报。虚报场景改由 `tests/test_agent.py::test_false_save_claim_is_rejected_then_corrected` 用脚本模型来覆盖。

## 模型根据工具结果调整动作：路径对比

| 对比 | 相同的起点 | 不同的工具结果 | 模型的后续动作 |
|---|---|---|---|
| **路径 A：版权补查** | M06、M07 的 `check_rules` 都返回 `needs_lookup` | `lookup_license`：TRK-2201 为 `expired`，TRK-3105 为 `valid` | M06 转为阻断、不查时段、不保存（[04](../examples/runs/deepseek/04_rule_risk/trace.md)）；M07 继续查时段并保存（[01](../examples/runs/deepseek/01_normal/trace.md)） |
| **路径 B：时段冲突** | M01、M05 的 `check_slot` 都显示被占用 | 输入中一个为 `flexible`，一个为 `hard` | M01 调用 `list_free_slots`，以待确认状态保存到 19:00；M05 只查建议时段，不保存，请求确认（[02](../examples/runs/deepseek/02_slot_conflict/trace.md)） |
| **路径 C：护栏反馈** | 模型尝试 `save_draft` | 07 返回 `slot_conflict`（被同批 M02 占用）；03 返回 `missing_requested_slot` | 07：改为调用 `list_free_slots`，保存到 19:00 并待确认；03：放弃保存，只给建议时段 |
| **路径 D：保存失败** | 两次运行都在 `save_draft` 返回 `tool_unavailable` | 08 一直失败，09 只失败 1 次 | 08：重试 1 次后停止，报告 `save_failed`；09：重试成功，`completed` |

## 发现的问题与修复（真实模型运行中暴露）

修复前的 Trace 保留在 [examples/runs/deepseek_before_fix/](../examples/runs/deepseek_before_fix/) 作为证据。

1. **补查结果没有反映到规则检查里，导致多余调用和误判的确认项。**
   - 第一次运行时，`check_rules` 是无状态的。补查得到 `valid` 或 `expired` 之后再调用，仍然返回 `needs_lookup`。
   - 后果：07 里模型又补查了一次，还在 M07 上多加了一条"请人工确认版权状态"；04 里多调用了一次 `check_rules`。
   - 修复：`ToolBox` 记录本次运行已补查过的 `track_id`，`check_rules` 据此给出结论，见 `tools.py` 中的 `looked_up`。
   - 新增测试 `test_check_rules_reflects_license_lookup`。修复后 07 的确认项只剩改期这一条。
2. **缺发布时间时，模型自选时段保存了草稿。**
   - 第二次运行 03 时，M02 的 `requested_slot=null`，模型自己选了 `2026-11-05 10:00` 并保存为待确认草稿。第一次运行却没有保存，同一输入、`temperature=0`，行为仍不稳定。
   - 原护栏只判断"时段与要求不同"，要求为 null 时没有拦住。
   - 修复：`save_draft` 在缺少要求时段时返回 `missing_requested_slot`；新增测试 `test_guard_missing_requested_slot`。
   - 修复后重跑，模型尝试保存被拒，随即改为只给建议（路径 C）。

## 已知限制

- **真实模型输出不完全可复现。** 即使 `temperature=0`，重跑后工具调用的顺序和条数也可能变化，问题 2 就是例子。关键约束因此放在代码护栏里，而不是依赖提示词。
- **Mock 只验证流程。** `examples/runs/mock/` 的分支是手写的规则，不代表模型的决策能力。
- **事后校验的范围有限。** 它覆盖保存状态、时段、审核结论、遗漏项和"已发布"类表述。自由文本（如 `decision_basis`）只做关键词检查，不做语义校验。
- **排期范围简化。** 只支持单日、整点、每渠道每时段 1 条；没有跨日推荐，也没有优先级或流量权重。
- **草稿库是本地 JSON 文件。** 写入是原子替换，但没有并发锁，多进程同时写可能丢失更新。生产环境应换成带唯一约束的数据库。
- **没有续跑能力。** 达到上限时返回 `incomplete` 和已核实的部分结果；已保存的草稿因为幂等可以安全重跑，但不会从中断点续跑。
- **测试规模。** 真实模型在每个用例上只跑了 1 次（05 跑了 2 次），没有做多次采样的稳定性统计。
