# CAIL 2026 · 智能合同审查（赛道三）

> 赛事：**CAIL 2026「智能合同审查」**（金山软件 × 武汉大学承办）。
> 任务：读带段落编号的合同，做**错误定位**与**条款修订**，产出两份合法 JSONL。

## 任务与评分
- **四类错误**：`typo`（错别字）、`inconsistency`（上下文不一致）、`missing_element`（要素缺失）、
  **`stance`（立场失衡/显失公平，复赛新增）**。
- **评分**（复赛实测反推，逐位吻合）：
  ```
  L（定位）= 10·Loc_typo + 20·Loc_inc + 40·Loc_missing + 30·Loc_stance
  R（修订）= 10·Rev_typo + 20·Rev_inc + 40·Rev_miss + 30·Rev_stance
  Total = 0.5·L + 0.5·R            # 权重 typo:inc:missing:stance = 1:2:4:3
  ```
- **提交**：zip 内固定两文件 `localization_predictions.jsonl`（3 字段）+ `revision_predictions.jsonl`（5 字段）；
  硬约束见 `docs/提交检查清单.md`（不满足会**整包退回**）。

## 当前成绩
| 阶段 | 提交 | Total | Loc | Rev | 备注 |
|---|---|---:|---:|---:|---|
| 初赛 | agent 包 | 27.9754 | 47.53 | 8.42 | 超官方基线 25.09 |
| 复赛 | semi_full | 22.0875 | 30.89 | 13.28 | 首版（stance 5.57） |
| 复赛 | **semi_kdeep** | **27.6117** | **40.42** | 14.81 | stance 20.93（+5.52） |

> 详细台账：`docs/提交台账.md`。

## 架构（单层确定性 workflow + 可插拔 Stage）
```
S0 解析 → S1 归一化底稿 → S2 事实抽取 → S3 空缺检测 → S4 定位(+stance 穷举)
        → S5 归类 → S6 句级改写 → S7 纯规则复核 → S8 合法性检查 → 输出
```
- **内核** `src/cail_race2/`：事实、检测、修订、评测的模块化实现（28 模块）；
- **Agent 作业** `agent/` + `mcp_eval/` + `skills/`：从 0 构建的 Agent（read/write/shell + MCP + CLI/WebUI + 两个 Skill）；
- 设计细节：`docs/设计形态.md`；技术方案：`docs/技术方案.md`；仓库结构：`docs/仓库结构.md`。

## 快速开始
```bash
pip install -e .                       # 安装内核
cp .env.example .env                   # 填 CAIL_API_KEY / BASE_URL / MODEL（key 不入库）

python -m pytest -q                    # 186 单测

# 出包（并行）——初赛/复赛用各自 contracts.jsonl
python scripts/agent_bench_parallel.py \
  --contracts resources/datasets/race2_semifinal/data/contracts.jsonl \
  --out outputs/semi_kdeep --provider ksxc --model deepseek-v4.1-flash --workers 16 --force

# 提交门禁（0 ERROR 才允许交）
python scripts/preflight_submit.py \
  --contracts resources/datasets/race2_semifinal/data/contracts.jsonl \
  --localization outputs/semi_kdeep/localization_predictions.jsonl \
  --revision outputs/semi_kdeep/revision_predictions.jsonl

# 本地官方口径回归（初赛 / 复赛）
python scripts/eval_samples.py            # 初赛 2 gold
python scripts/eval_samples.py --semifinal  # 复赛 5 gold

# Agent / WebUI
python cli.py agent --contract <f.jsonl> --out <dir>
python cli.py webui --port 8800
```

## 目录速览
```
src/cail_race2/   内核（管线/检测/修订/评测）
agent/ mcp_eval/ skills/   Agent 作业（工具 / MCP 服务 / 技能）
scripts/          出包 · 评测 · 门禁 · 对照
tests/            34 文件 · 186 用例
docs/             技术方案 / 设计形态 / 台账 / 漏检清单 / 检查清单
resources/        官方资料 + 数据集（复赛数据与 .env 不入库）
```

## 安全与纪律
- **API key 只放 `.env`**（已 gitignore），不进代码/日志/repr/仓库；
- 复赛数据（`resources/datasets/race2_semifinal/`）与打包产物（`dist/`）**不入公开仓库**；
- 提交前必跑 `preflight_submit`（格式硬约束）+ `pytest`。

## 许可
竞赛与课程用途；引用的官方规则/数据版权归主办方。
