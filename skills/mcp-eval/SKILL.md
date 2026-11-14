---
name: mcp-eval
description: 通过 MCP 连接器发现评测服务工具，按服务要求的字段、类型和结构组织测评输入，校验并构建请求，解析返回结构中的评分与反馈。Use when 需要对一份合同的审查结果做一次真实 MCP 测评、取回评分。
---

# 测评 Skill（MCP）

## 目标
把审查结果交给评测服务（MCP Server）评分，并解析返回的**评分与反馈**。

## 步骤

1. **发现工具定义**：从 MCP 连接器拿到工具列表（`tools/list`），关注：
   - `submit_contract_review` / `get_review_result`（异步入队 + 取分）
   - `score_review`（同步直接评分）
2. **对齐输入结构**（严格按 schema，字段名/类型不得自造）：
   | 字段 | 类型 | 说明 |
   | --- | --- | --- |
   | `contract_id` | string | 合同编号 |
   | `context` | string | 合同原文（含 `<p id>` 标签） |
   | `localization` | array | 定位记录：`{contract_id, location, error_type}` |
   | `revision` | array | 修订记录：`{contract_id, location, error_types, original_text, correct_answer}` |
3. **校验并构建请求**：`location` 为升序不重叠区间数组；`original_text` 必须与输入段落逐字一致；
   `error_types` 须等于该段定位类型并集。
4. **调用并解析**：读回 JSON 的 `score` / `mode` / `breakdown` / `feedback`，向用户报告分数与问题。

## 注意
- 若服务返回 `isError` 或 `error`，先校验入参结构再重试，不要盲目重发。
- 评分口径：有 gold 时按 CAIL L/R/Total；否则为自检分（结构合法性 + 修订后残余问题）。
