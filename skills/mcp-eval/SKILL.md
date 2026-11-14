---
name: mcp-eval
description: 通过 MCP 连接器发现评测服务工具，按服务要求的字段、类型和结构组织测评输入，校验并构建请求，解析返回结构中的评分与反馈。Use when 需要对一份合同的审查结果做一次真实 MCP 测评、取回评分。
---

# 测评 Skill（MCP）

## 目标
把一份合同的审查结果交给评测服务（MCP Server）评分，并**解析返回的评分与反馈**，向用户报告。

## 步骤

### 1. 发现工具定义
从 MCP 连接器取得工具列表（`tools/list`），识别本服务暴露的工具：

| 工具 | 用途 |
| --- | --- |
| `score_review` | 同步直接评分（推荐，一步拿分） |
| `submit_contract_review` | 异步入队，返回 `task_id` |
| `get_review_result` | 按 `task_id` 取回评分结果 |
| `list_rubric` | 返回评分口径说明 |

### 2. 对齐输入结构（严格按 schema，字段名/类型不得自造）
| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `contract_id` | string | 合同编号 |
| `context` | string | 合同原文（含 `<p id>` 标签） |
| `localization` | array | 元素 `{contract_id, location, error_type}`；`location` 升序不重叠区间 |
| `revision` | array | 元素 `{contract_id, location, error_types, original_text, correct_answer}`；`original_text` 须与输入段落逐字一致 |

### 3. 校验并构建请求
调用前自查：
- `location` 区间升序、不重叠、编号存在；
- `error_types` == 该 PID 的定位类型并集；
- `original_text` 与原文逐字一致；`correct_answer` 非空、无段落标签；
- 同一 PID 不重复修订。
> 可直接调用工作区能力 `load_review(contract, out)` 生成上述完整入参 JSON。

### 4. 调用并解析
```
调用：score_review(contract_id, context, localization, revision)
返回（JSON 文本）：
{
  "score": 97.8571,
  "mode": "cail_gold",           # 或 "self_check"
  "breakdown": {"Localization": 95.71, "Revision": 100.0,
                "Loc_typo": 100, "Loc_inconsistency": 85.71, "Loc_missing": 100,
                "Rev_typo": 100, "Rev_inconsistency": 100, "Rev_missing": 100},
  "feedback": "按 CAIL 口径评分。结构校验通过。"
}
```
解析要点：
- `mode="cail_gold"`：有标准答案，按 CAIL 口径（定位 1:3:6、修订 10:30:60）给出 `Localization/Revision/Total`；
- `mode="self_check"`：无标准答案，给出结构合法性 + 修订后残余问题的自检分；
- 逐项读 `breakdown`，指出**最低分项**作为改进方向，并在答复中转述 `feedback`。

## 错误处理
- 返回 `isError` 或 `error` 时：**先校验入参结构**（字段名/类型/区间/逐字一致），再重试，不要盲目重发。
- `get_review_result` 报 `task 不存在`：确认 `task_id` 是否来自同一次会话的 `submit_contract_review`。
- 连接/进程异常：确认 MCP server 可启动（`python -m mcp_eval.server`）。

## 注意
- 评分口径以服务返回为准，不要自行折算分数。
- 报告分数时同时给出交付文件路径（批注合同、审查报告、两份 JSONL）。
