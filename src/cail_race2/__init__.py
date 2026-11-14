# -*- coding: utf-8 -*-
"""CAIL 2026 赛道三 · 智能合同审查（错误定位与条款修改）最小框架。

模块：
- contracts  读合同、解析段落
- records    提交记录数据类与校验（不变量）
- llm        DeepSeek（OpenAI 兼容）客户端
- prompts    提示词（占位，方案确定后重写）
- predictor  预测器接口 + LLM/空实现 + 响应归一化
- submission 原子写 JSONL、打包 zip
- pipeline   端到端编排（带逐合同缓存）
"""
