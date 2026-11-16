# 项目工作规约（CAIL 2026 赛道三 · 智能合同审查）

> 本文件是**项目级**规约，优先于通用习惯。开工先读本文件与 `docs/状态.md`。

## 0. 最高优先：先讨论，后改代码（2026-11-16 用户确立）

**流程已趋复杂，代码频繁改动会破坏能力稳定性。因此：**

1. **任何 issue 在动代码前必须充分讨论**，至少覆盖：
   - **目标**（要提升哪个线上分项、期望多少）；
   - **依据**（线上证据 / 可复现实验，而非"看起来合理"）；
   - **验收**（改完用什么**可观测**指标判定成败）；
   - **风险与回退**（失败如何回退、是否默认关闭）。
2. **单变量原则**：一次只改一项，其余保持不变。
3. **只认线上可观测增量**：`docs/召回分析.md` 阶段六已证——我们用模型标注自建的离线代理指标**与线上不一致**（离线 +0.06 却线上 −3.08）。**禁止**用离线标注代理作为决策依据（只可作防退化回归）。
4. **改动必须可回退**：新能力用构造函数 flag / 参数开关，**默认关闭**；失败的代码路径**保留不删**并注明原因。
5. **尊重榜单噪声**：未改动分项在 R2→R3 间波动 +1.2~+5.6 → 单次提交 ±0.5~1.0 属噪声；**判断"涨"必须多次提交或对比同配置**。

## 1. 关键结论（速查）

| 主题 | 结论 | 详见 |
|---|---|---|
| 计分权重 | `typo:inc:missing:stance = 1:2:4:3`，`Total=0.5L+0.5R`（R1/R2/R3 三次逐位吻合） | `docs/提交台账.md` |
| 榜单展示的 `Typo_TP/FP/FN` | 属**修订侧**（`Rev_typo=F0.5(TP,FP,FN)` 精确吻合），**不是**定位口径 | `docs/召回分析.md` 阶段一 |
| 5 份 gold | 是**干净演示集**，本地高估 4–6 倍，**不能作召回基准** | 同上 |
| 唯一有线上正向证据的改动 | **missing 结构化补齐**（主体信息对等/收款账户/开票信息）→ Loc_missing +1.59 | `docs/召回分析.md` 阶段六 |
| 已证有害（默认关闭） | stance 滥报过滤 / 对等性配对 / S7.5 跨模型审稿；typo 后置校验完整规则 | `docs/召回分析.md` 阶段六 |
| typo 现状 | 线上 `Rev_typo 59.9`、精 57%/召 75%；后置校验降级为**仅空白保真** | `docs/typo优化.md` |
| 收益重心 | **R（修订）侧**：Rev 合计仅 15.5 / Loc 40.3 → R 有 84.5 余量，但需"匹配 gold 写法" | `docs/状态.md` |

## 2. 交付与安全纪律

- **API key 只在 `.env`**（gitignore）；**任何**代码/日志/文档/repr 不得含 key。
- **复赛/封测数据不入公开仓库**：`resources/datasets/race2_semifinal/`、`resources/typo/contract/`、`resources/recall/`、`outputs/`、`dist/` 均 gitignore。
- 提交前必跑：`pytest -q` + `scripts/preflight_submit.py`（0 ERROR 才允许交）。
- `resources/official/` 为官方只读存档，不写入。

## 3. 常用命令

```bash
python -m pytest -q                                     # 222 单测
# 出包（45 合同）
python scripts/agent_bench_parallel.py \
  --contracts resources/datasets/race2_semifinal/data/contracts.jsonl \
  --out outputs/<name> --provider ksxc --model deepseek-v4.1-flash --workers 16 --force
# 门禁 / 召回检测 / typo 验证
python scripts/preflight_submit.py --contracts <f> --localization <f1> --revision <f2>
python scripts/recall_check.py --all --localization <f>
python scripts/typo_validate.py --annot resources/typo/contract/typo_set.jsonl --contracts <f> --localization <f1> --revision <f2>
```
