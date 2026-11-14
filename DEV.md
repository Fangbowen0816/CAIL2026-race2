# 开发说明 · CAIL 2026 赛道三「智能合同审查」

> 最小框架（已在 2026-11-14 跑通 mock 流程）。具体方案（提示词/解码/评测）待定。

## 目录

```
CAIL2026/
├── resources/                       # 只读：官方资料 + 数据集（见 resources/official/2026/README.md）
├── src/cail_race2/
│   ├── contracts.py   # 读合同、解析 <p id> 段落
│   ├── records.py     # 定位/修订记录数据类 + 不变量校验
│   ├── llm.py         # DeepSeek（OpenAI 兼容）客户端；key 只走环境变量
│   ├── prompts.py     # 提示词（占位，方案确定后重写）
│   ├── predictor.py   # Predictor 接口 + NullPredictor + LLMPredictor + 响应归一化
│   ├── submission.py  # 原子写 JSONL + 打包 zip
│   └── pipeline.py    # 端到端编排（逐合同缓存，可断点续跑）
├── scripts/
│   ├── run_prelim.py          # 跑初赛：预测 → 两份 JSONL → zip
│   ├── validate_submission.py # 提交格式自检（按赛道校验口径）
│   └── eval_examples.py       # 在「提交示例」gold 上本地打分
├── tests/                     # 单测（解析/不变量/协议映射/错误路径/原子写/评测）
├── .env.example               # 复制为 .env 填写（.env 已被 gitignore）
└── pyproject.toml
```

## 使用

```bash
# 1) 离线跑通（不调模型）
python scripts/run_prelim.py --mock

# 2) 配置 key（PowerShell：$env:CAIL_API_KEY="sk-..."；或复制 .env.example 为 .env）
python scripts/run_prelim.py                 # 全量
python scripts/run_prelim.py --limit 2 --force

# 3) 自查提交格式（exit 1 = 有 ERROR）
python scripts/validate_submission.py \
  --contracts resources/datasets/race2_contract_review/contracts.jsonl \
  --localization outputs/prelim/localization_predictions.jsonl \
  --revision     outputs/prelim/revision_predictions.jsonl

# 4) 本地打分（先 mock，再真模型；也可对已有提交打分）
python scripts/eval_examples.py --mock
python scripts/eval_examples.py
python scripts/eval_examples.py --pred-dir outputs/prelim
```

跑测试：`python -m pytest -q`

## 环境变量（勿写入代码/仓库/日志）

已实测确认（2026-11-14）可用配置：

| 变量 | 说明 | 默认 |
| --- | --- | --- |
| `CAIL_API_KEY` | 必填；回退 `DEEPSEEK_API_KEY` / `KSXC_AUTH_TOKEN` | — |
| `CAIL_BASE_URL` | OpenAI 兼容端点 | `https://shared.kscc.api.ksyun.com/v1` |
| `CAIL_MODEL` | 模型 id | `deepseek-v4.1-flash` |
| `CAIL_HEADERS` | 额外请求头 JSON（ksxc 网关必需 `ksyun-code-type: ksxc-cli`） | `{"ksyun-code-type":"ksxc-cli"}` |
| `CAIL_JSON_MODE` | 是否用 `response_format=json_object` | `1` |

- 已验证：`GET /cli/models` 返回含 `deepseek-v4-flash / deepseek-v4-pro-0813 /
  deepseek-v4.1-flash / glm-5.3 / glm-5.3-flash / kimi-k3`；
  `POST /chat/completions`（model=`deepseek-v4.1-flash`）返回 200。
- 最小必需头：`ksyun-code-type: ksxc-cli`（缺少则 403 ApiKeyForbidden）。

## 已实现的关键不变量

- 段落解析：`<p id="N">…</p>`，正文可跨行/为空；
- location 必须是升序、互不重叠的闭区间，编号必须存在；
- 空 location ⇔ 无问题哨兵（定位 `error_type=null`；修订全空）；
- 修订：单点区间、`original_text` 回填原文并校验逐字一致、`correct_answer` 非空无标签、同 PID 去重；
- 原子写 JSONL（临时文件 + `os.replace`），逐合同缓存可续跑；
- API key 不进 repr、不进异常信息。

## 待定（下一步与你确认）

1. 提示词策略：单合同两阶段 vs. 分段定位；是否 few-shot（可用 `提交示例/` 的 C001/C002）；
2. 本地评测当前是近似口径（官方脚本不公开），后续可加密：ChERRANT 字级 F0.5、多参考一致性、
   LLM-as-a-Judge；
3. 15 份初赛合同**无 gold**，本地只能靠 2 份示例 + 官方榜分迭代。
