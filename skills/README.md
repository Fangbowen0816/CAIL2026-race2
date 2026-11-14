# Skills（技能）说明

本目录是 Agent 的**技能包**，采用**渐进式披露（progressive disclosure）**：
- Agent 启动时只把每个技能的 `name + description` 注入系统提示（目录摘要）；
- 任务匹配后，用 `read_file` 读取对应 `SKILL.md` 全文，再按其中步骤执行；
- 需要时才读 `references/` 下的细节。

## 技能清单

| 技能 | 用途 | 入口 |
| --- | --- | --- |
| `contract-review` | 审查中文合同：定位三类问题 → 产出批注合同、审查报告、两份 JSONL | `SKILL.md`；细则见 `references/` |
| `mcp-eval` | 通过 MCP 连接器发现评测工具、对齐 I/O、调用并解析评分 | `SKILL.md` |

## 目录约定
```
skills/<skill-name>/
├── SKILL.md            # 必需：YAML frontmatter(name, description) + 方法正文
└── references/         # 可选：细节参考、模板、清单
```

## 编写约定
- `description` 写「做什么 + 何时用（Use when …）」，便于目录匹配。
- 正文给**可执行的步骤**与**产出规格**，避免空泛描述。
- 与仓库能力一致：优先用 `run_shell` 调用现有脚本，而非让模型手写脚本。
