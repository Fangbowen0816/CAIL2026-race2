# CAIL 2026 官方资料（已拉取）

> 拉取时间：2026-11-14（北京时间）
> 来源：<http://cail.cipsc.org.cn/> 与公开 API `/api/*`（无需登录）
> 拉取脚本：`../../fetch_official.py`（可重跑刷新）

## 目录

```
official/2026/
├── README.md                # 本文件
├── site_overview.json       # 2026 四赛道总览（本站前端静态数据）
├── notices_global.json      # 全局通知（含 CAIL 2026 开赛通知）
├── race2_contract_review/   # 赛道 03 智能合同审查（金山软件 + 武汉大学承办）★ 本仓库目标
│   ├── detail.md            # 赛题说明（任务/数据/评分/提交/封测接口）★ 权威口径
│   ├── join.md              # 参赛对象与报名方式
│   ├── timeline.md          # 赛程时间线
│   ├── reward.md            # 奖项
│   ├── taskInfo.json        # 标题 + 简介
│   ├── raceInfo.json        # 上述四项原始 JSON
│   ├── stageName.json       # 三阶段配置、提交限制、评分项名
│   ├── stageInfo.json       # 阶段列表（同 stageName 精简）
│   ├── timePeriod.json      # 阶段起止时间
│   ├── prizeList.json       # 奖金档位
│   ├── notices.json         # 本赛道通知（当前为空）
│   └── datasetList.json     # 数据集列表（需登录，见下）
```

## 关键事实（race2 智能合同审查）

- **两个子任务**：① 错误定位与识别（typo / inconsistency / missing_element，定位到段落 id）；
  ② 合同条款修改（返回实际修改段落的完整最终文本）。
- **计分**：`L = 10·F_t + 30·F_c + 60·F_m`（定位）；`R = 10·T + 30·C + 60·M`（修改）；
  `S = 0.5·L + 0.5·R`。定位加权 **错别字:不一致:要素缺失 = 1:3:6**。
- **晋级线**：初赛需超过官方基线 **Qwen3.8-27B，总分 25.09**（定位 32.01 / 修改 18.17）。
- **阶段权重**：最终成绩 = 初赛 10% + 复赛 30% + 封测 60%。
- **时间**：初赛 2026.10.15–11.15 ｜ 复赛 11.15–12.20 ｜ 封测 12.20–12.31。
- **提交**：zip 内固定两个文件 `localization_predictions.jsonl` + `revision_predictions.jsonl`。
- **复赛口径变化（实测反推）**：新增错误类型 **`stance`（立场失衡/显失公平）**；
  四类权重为 **typo:inconsistency:missing:stance = 1:2:4:3**（初赛的 1:3:6 已不适用）。
  另：**定位的 stance 段必须有修订记录**（`correct_answer` 可为 null）。
- **封测**：自行部署推理服务，提交 `{"api_key": "...", "headers": {...}}`；平台逐份合同 POST
  `{contract_id, context}`，期望返回 `{contract_id, localization, revisions}`。

## 本地数据集（已就位）

来源：`D:\下载\cail2026_智能合同审查-初赛阶段-数据集.zip`
已解压到 `../../datasets/race2_contract_review/`：

```
resources/datasets/race2_contract_review/
├── cail2026_race2_prelim.zip        # 原始压缩包副本
├── contracts.jsonl                  # 初赛输入：15 份合同（CAIL-001 ~ CAIL-015）
├── 提交示例/
│   ├── contracts.jsonl              # 2 份示例合同（C001/C002）
│   ├── localization_predictions.jsonl  # 定位提交示例（6 行）
│   └── revision_predictions.jsonl      # 修订提交示例（6 行）
└── CAIL2026智能合同审查-保密承诺书.doc
```

- 初赛输入仅 `{contract_id, context}`，`context` 用 `<p id="PID">正文</p>` 标注段落；
  15 份合同段落数 44–175。
- 提交需 zip 包内固定两文件：`localization_predictions.jsonl` +
  `revision_predictions.jsonl`（字段与格式见 `提交示例/` 与 `detail.md`）。
- 该赛道**不提供**官方评分脚本/参考解，评分由平台完成。
