# 04 AI 辅助说明

## 使用的工具

- **Claude Code**（Anthropic，VS Code 扩展），在本仓库中直接读写文件、运行命令。
- **DeepSeek `deepseek-chat`**：这是被测 Agent 的运行时模型，不是开发辅助工具。

## AI 生成的内容

| 范围 | 说明 |
|---|---|
| 选题建议 | AI 分析四道题后建议选题 1，理由是验收点能用确定性工具验证、护栏和幂等可以测试 |
| 代码 | `src/` 全部模块、`main.py` 的初稿由 AI 生成 |
| 合成数据 | `data/` 下的素材、规则、排期由 AI 按验收点设计 |
| 测试 | `tests/` 由 AI 编写，包括用脚本模型模拟"虚报保存"等错误行为 |
| 文档 | README 与 docs/01–05 的初稿由 AI 撰写 |
| 问题发现与修复 | 真实模型运行后，AI 阅读 Trace 发现两个问题（补查结果未反映、缺时间时被自选时段保存），并完成修复、补测试、重跑。详见 03-evaluation.md |

## 验证过程（已实际执行）

- `python -m pytest -q`：31 个测试全部通过。
- `python main.py examples --mock` 与 `python main.py examples`：在 DeepSeek 上跑完全部用例。逐条阅读 `trace.md`，并核对 `drafts_after.json` 中的草稿数量与状态。
- 修复问题后重跑受影响的用例，修复前的 Trace 保留在 `examples/runs/deepseek_before_fix/`。

## 本人工作

**选题决策**

AI 分析四道题后推荐题 1，核心理由是"验收点都可以用确定性工具验证"。我认同这个判断——题 1 的正确性（冲突有没有被拦、是否真的没发布、草稿是否幂等）都可以通过代码层面的测试来证明，而题 3（知识问答）或题 4（短视频脚本）的测试结果更依赖主观判断。基于这个认识，我选择了题 1。

**环境配置与运行**

- 本机 Python 版本为 3.15 alpha，AI 发现后改用 uv 自带的 3.13 建虚拟环境，我确认了这个决策是合理的。
- 申请了 DeepSeek API Key，在本地创建 `.env` 文件并填写 Key。这是本项目中唯一我独立完成、AI 无法代劳的步骤。
- 在本机执行了全部命令：`python -m pytest -q`、`python main.py examples --mock`、`python main.py examples`，观察输出并确认结果符合预期。

**阅读与理解**

逐段阅读了以下模块，能够讲清其设计：

- [tools.py](../src/schedule_agent/tools.py) 的护栏部分：`save_draft` 内嵌了五条硬约束（冲突时段、硬性时间、阻断素材、缺发布时间、改时段必须待确认），模型即使判断错了也会被代码拒绝，收到明确的错误信息后自己调整。
- [store.py](../src/schedule_agent/store.py) 的幂等设计：唯一键是 `(material_id, channel)` 而不是请求 ID，原因是同一素材在不同请求中可能改变时段，用请求 ID 做键会产生多份草稿，而业务语义上同一渠道只能有一份草稿。
- [verifier.py](../src/schedule_agent/verifier.py) 的校验逻辑：`check_submission` 在模型提交结论时核对工具账本，不一致就打回；`reconcile` 在最终报告时以工具事实覆盖，并写入 `corrections`。这样即使模型"撒谎"，报告中体现的也是真实结果。

**决策确认**

- AI 建议不使用任何 Agent 框架，理由是所需功能只有"工具调用循环 + 上限 + 校验"，原生实现便于测试和讲解。我认同，并确认了这在面试时更容易解释每处取舍。
- 阅读 Trace 后，我确认了 AI 发现的两个问题（补查结果未反映、缺时间时自选时段）确实存在于 `examples/runs/deepseek_before_fix/` 中，且修复后重跑结果正确。
- 更新了 [docs/05-retrospective.md](05-retrospective.md) 中的实际用时。

**我能解释的几个关键设计取舍**

以下是阅读代码后，我理解并认同的设计选择，可以在面试中展开讨论：

*为什么护栏放在工具代码里，而不是只写在系统提示词里？*

提示词约束模型的行为，但当 `temperature=0` 的模型在不同运行里仍然出现不一致行为（如 03 用例里缺时间时有时保存有时不保存），就说明仅靠提示词不够稳定。把护栏写进 `save_draft` 的代码层，无论模型怎么决策，错误的动作都会被拒绝，并且模型收到的是明确的错误码（如 `missing_requested_slot`、`slot_conflict`），而不是模糊的"不允许"——这让模型更容易根据反馈调整下一步，也更容易在测试里验证护栏确实生效。

*为什么用 `(material_id, channel)` 做幂等键而不是用请求 ID？*

用请求 ID 做幂等意味着同一素材换了时段重新提交会产生两份草稿，草稿库会出现同一渠道两个时段都有排期的情况，这不符合"每条内容在每个渠道同一时间只有一个排期"的业务逻辑。用 `(material_id, channel)` 做键，更新时原地修改版本号并把旧时段写入 `history`，能同时满足"重复提交只有一份"和"改期后原草稿被更新"两个验收点。

*为什么最终报告要经过 `reconcile` 而不直接用模型提交的结论？*

模型的 `submit_result` 可能在自由文本字段里出现错误（比如用了"已发布"的表述，或 `draft_status` 与实际调用不符）。`check_submission` 先把错误返回给模型让它自己修正（最多 2 次），之后仍然不一致的由 `reconcile` 用工具账本的真实结果覆盖。这样最终输出给用户的报告有独立的事实来源，不完全依赖模型的表述。这在 `test_false_save_claim_is_rejected_then_corrected` 测试里有直接验证。

**Trace 核对记录**

人工核对了以下几条，逐一对应了工具调用和最终输出：

- **02_slot_conflict**：M01 的 `save_draft` 参数里 `needs_confirmation=true`，`confirmation_items` 里写明了原因；M05 没有调用 `save_draft`，`drafts_after.json` 里只有 M01 一条草稿。
- **05_duplicate run2**：`save_draft` 的返回摘要显示 `duplicate v1`，草稿的 `draft_id` 与 run1 完全一致，`drafts_after.json` 里仍是 1 条记录。
- **06_reschedule**：草稿 `version=2`，`history` 里保留了上一次的时段 `20:00`，`slot` 字段已更新为 `19:00`。
- **08_save_failure**：两次 `save_draft` 都返回 `tool_unavailable`，模型在第二次失败后直接提交，`draft_status=save_failed`，`drafts_after.json` 为空数组。

## AI 使用的边界

- 所有运行结果均来自真实执行，Trace 由程序自动生成，未手工编辑。
- `.env` 中的 API Key 由本人在本地配置，AI 未读取，也未提交到仓库。
