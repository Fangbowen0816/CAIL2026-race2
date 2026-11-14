# Agent 系统 · CAIL 2026 合同审查（课程实践作业）

> 对齐课件最后一页「实践作业」：从 0 构建 Agent，用两个 Skill 串联合同审查与 MCP 测评。
> Agent 内部使用 **ksxc（金山云码）provider**，模型 **deepseek-v4.1-flash**。

## 1. 架构

```
CLI / WebUI  ──►  Agent 宿主（agent/loop.py，LLM + tool_calls）
                     │  tools: read_file / write_file / list_dir / run_shell
                     │  task tools: review_contract / load_review
                     │  skills: contract-review, mcp-eval（渐进式披露）
                     ▼
          ┌── 合同审查能力（agent/review.py，复用 cail_race2 内核）
          │     确定性预分析(facts/verify) → LLM 定位(detect) → LLM 修订(revise)
          │     + 确定性算术修复(repair) → 批注合同 / 审查报告 / 两份 JSONL
          ▼
    MCP 评测服务（mcp_eval/server.py，stdio JSON-RPC）
          tools: submit_contract_review / get_review_result / score_review / list_rubric
          返回 {score, mode, breakdown, feedback}
```

- **Agent 宿主**：自实现 tool-calling 循环（`agent/loop.py`），不做 LLM 编排控制流（固定步骤由 Skill 约束）。
- **MCP 连接器**：`agent/mcp_client.py`，自实现最小 MCP stdio 协议（initialize / tools/list / tools/call）。
- **Skill**：`skills/contract-review/SKILL.md`（审查方法 + 产出要求）、`skills/mcp-eval/SKILL.md`（发现工具、对齐 I/O、解析评分）。

## 2. 目录

```
agent/            # Agent 宿主：config / llm 复用 / tools / mcp_client / skills / loop / review / webui
mcp_eval/         # MCP 评测服务：server.py（stdio JSON-RPC）+ scorer.py（评分）
skills/           # 两个 Skill（SKILL.md + references）
cli.py            # 统一入口：review / agent / accept / benchmark / webui
src/cail_race2/   # 合同审查内核（确定性 + LLM），含 repair.py
scripts/agent_bench_parallel.py  # 并行跑 CAIL 基准
```

## 3. 运行方式

```bash
# 验收链：审查 → MCP 评分 → 交付（复用内核，稳定）
python cli.py accept --contract resources/datasets/race2_contract_review/提交示例/contracts.jsonl --out outputs/agent_accept

# LLM Agent 自主跑链（Agent 读 Skill、经工具完成审查并调用 MCP）
python cli.py agent  --contract resources/datasets/race2_contract_review/提交示例/contracts.jsonl --out outputs/agent_loop

# 批量跑 CAIL 基准（并行，逐合同缓存），产出可提交 zip
python scripts/agent_bench_parallel.py --out outputs/agent_bench --workers 4 [--force]

# 网页入口
python cli.py webui --port 8800     # 打开 http://127.0.0.1:8800
```

## 4. 实测（2026-11-14）

- **验收链** `cli.py accept`（C001）：MCP 评分 **97.86**
  （Localization 95.71 / Revision 100；Loc_missing 100 / Rev_missing 100）——确定性算术修复生效
  （「2200→2000」「1100→1000」精确命中）。
- **验收链** `cli.py agent`：3 次工具调用完成
  `review_contract → load_review → score_review`，最终答复含 CAIL 口径评分与短板分析。
- **MCP 评分**：`score_review` 对有 gold 的合同返回 CAIL 口径（Localization/Revision/Total）；
  对无 gold 的返回自检分（结构合法性 + 修订后残余问题）。
- **并行基准**（ksxc `deepseek-v4.1-flash`，4 workers，15 份）：
  定位 **284** 条、修订 **244** 条；`validate_submission` **0 ERROR / 0 WARN**；
  提交包 `outputs/agent_bench/cail2026_race2_submission.zip`。

## 5. 任务 B 增强（承接平台分项短板）

平台初赛反馈：`Rev_missing 0.22`、`Loc_missing 29.01` 为最大失分项。本次针对性增强：

- **确定性算术修复** `repair.py`：单价×数量≠总价 / 比例×总价≠金额 → 直接重写数值，
  并归入 `inconsistency`（C001 实测把「2200→2000」「1100→1000」精确修对）。
- **要素缺失线索** `verify.find_slot_gap_candidates`：交付/付款类条款段内无时间 → 作为
  hints 提示 LLM 主动查 missing（不强制判定，保精度）。
- **提示词**：新增 missing 主动排查规则与 few-shot 口径示例。
- **鲁棒性**：LLM 空响应重试；detect/revise 失败降级为确定性结果；批量任务单合同失败不中断。

## 6. 配置（ksxc）

`agent/config.py` 优先级：环境变量 → `~/.pi/agent/models.json` → `~/.ksxc/auth.json`。
base_url `https://shared.kscc.api.ksyun.com/v1`，必需头 `ksyun-code-type: ksxc-cli`，模型 `deepseek-v4.1-flash`。
key 只从上述来源读取，不进代码/日志/repr。
