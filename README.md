# 素材审核与发布排期 Agent（题 1）

这个 Agent 帮内容团队审核待发布素材，并生成**无冲突、可确认的排期草稿**。它只保存草稿，不发布。

- 模型：DeepSeek `deepseek-chat`，通过兼容 OpenAI 的接口调用 function calling，可替换为其他兼容服务
- 实现：Python 原生 ReAct 循环，不依赖 Agent 框架
- 运行方式：CLI

## 评审入口

| 想看什么 | 去哪里 |
|---|---|
| 需求与验收标准 | [docs/01-requirements.md](docs/01-requirements.md) |
| 调用流程、动态决策、护栏设计 | [docs/02-solution.md](docs/02-solution.md) |
| 测试预期与实际结果 | [docs/03-evaluation.md](docs/03-evaluation.md) |
| 真实模型运行记录 | [examples/runs/deepseek/](examples/runs/deepseek/)，每个用例有 `trace.md`、`output.json` 和 `drafts_after.json` |
| 修复前的真实运行记录（问题证据） | [examples/runs/deepseek_before_fix/](examples/runs/deepseek_before_fix/) |
| 离线 Mock 运行记录 | [examples/runs/mock/](examples/runs/mock/) |
| 核心循环 | [src/schedule_agent/agent.py](src/schedule_agent/agent.py) |
| 工具与护栏 | [src/schedule_agent/tools.py](src/schedule_agent/tools.py) |
| 结果校验（防虚报） | [src/schedule_agent/verifier.py](src/schedule_agent/verifier.py) |

## 环境与安装

需要 Python 3.10 及以上（开发时用的是 3.13）。

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

## 配置

```bash
cp .env.example .env      # Windows: copy .env.example .env
# 编辑 .env，填写 LLM_API_KEY（DeepSeek key）
```

用 `--mock` 离线运行时不需要任何配置。

## 运行

```bash
# 1) 单个请求（真实模型）
python main.py run --input examples/inputs/02_slot_conflict.json --reset-store

# 2) 注入保存失败：save_draft 一直失败 / 只失败 1 次
python main.py run --input examples/inputs/08_save_failure.json --reset-store --fail save_draft
python main.py run --input examples/inputs/08_save_failure.json --reset-store --fail save_draft:1

# 3) 重复提交：不加 --reset-store 再运行一次，草稿库里仍只有一份草稿
python main.py run --input examples/inputs/05_duplicate.json --reset-store
python main.py run --input examples/inputs/05_duplicate.json

# 4) 步数上限
python main.py run --input examples/inputs/01_normal.json --reset-store --max-steps 3

# 5) 批量跑全部用例，结果写入 examples/runs/deepseek/（加 --mock 则写入 examples/runs/mock/）
python main.py examples
python main.py examples --mock

# 6) 测试（离线，不调用模型）
python -m pytest -q
```

默认草稿库位于 `.runtime/drafts.json`，可用 `python main.py reset-store` 清空。

## 评审可以自行改动的地方

- **改占用时段**：编辑 `data/schedule.json` 的 `occupied`，再运行 `02_slot_conflict`，观察建议时段是否随之变化。
- **改素材或规则**：例如把 `data/rules.json` 中 `TRK-2201` 的状态改为 `valid`，M06 应从阻断变为可排期。
- **改输入**：把 `time_requirement` 在 `hard` 和 `flexible` 之间切换，观察是请求确认还是保存替代时段。

## 目录

```
src/schedule_agent/   代码（agent / tools / store / verifier / llm / mock_llm / render / cli）
tests/                pytest：工具护栏 + Agent 循环 + 模拟模型犯错
examples/inputs/      输入请求
examples/cases.json   批量用例定义（含故障注入、重复运行、预置草稿）
examples/runs/        实际输出与 Trace（deepseek / mock）
data/                 合成素材、审核规则、已有排期
docs/                 01–05 文档
```

## Mock 的边界

`--mock` 用手写的固定策略代替模型，只用来证明循环、工具、护栏、校验和 Trace 这套流程能跑通，**不能证明真实模型的决策效果**。模型决策效果请看 `examples/runs/deepseek/`。
