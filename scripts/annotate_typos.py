# -*- coding: utf-8 -*-
"""用模型穷举标注合同内的错别字，建本地「错别字集」（作为检测模块的优化目标）。

用法：
  python scripts/annotate_typos.py --contracts resources/datasets/race2_semifinal/data/提交示例/contracts.jsonl \
      --out resources/typo/annot --provider ksxc --model deepseek-v4.1-flash --workers 4
  python scripts/annotate_typos.py ... --agg resources/typo/typo_set.jsonl   # 汇总去重
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, ROOT)

from agent.config import load_provider                        # noqa: E402
from cail_race2.contracts import load_contracts               # noqa: E402
from cail_race2.llm import LLMClient, extract_json            # noqa: E402

_SYS = """你是资深中文校对专家。任务：在给定合同全文中，**逐段逐字**找出**全部错别字/笔误**。

错误类型（全部要找）：
1. 同音错字（如 提共→提供、验受→验收）；2. 形近错字（如 已→己、鉴→签）；
3. 多字（重复字，如 送送达→送达）；4. 少字（如 不足弥补→不足以弥补）；5. 词序颠倒（如 要主→主要）。
标点重复（。。→。）也算，须报出。

**不要报**：合同术语、公司名/人名/地名等专有名词、法律用语、访谈式表达、
意思清楚只是不够专业的表述、以及"原文本来就这样且并非错误"的内容。

严格只输出 JSON：
{"typos":[{"pid":段落号整数,"wrong":"错误片段","right":"正确片段"}]}
没有错误则输出 {"typos":[]}。"""


def _messages(contract):
    lines = [f"p{pid}: {txt}" for pid, txt in sorted(contract.paragraphs.items()) if (txt or "").strip()]
    return [{"role": "system", "content": _SYS},
            {"role": "user", "content": "逐段找出全部错别字：\n" + "\n".join(lines)}]


def annotate(contract, client):
    obj = client.complete_json(_messages(contract), temperature=0.0)
    items = obj.get("typos") if isinstance(obj, dict) else None
    out = []
    for it in (items or []):
        if not isinstance(it, dict):
            continue
        pid, wrong, right = it.get("pid"), it.get("wrong"), it.get("right")
        if isinstance(pid, int) and pid in contract.paragraphs and wrong and right \
                and str(wrong) != str(right):
            out.append({"pid": pid, "wrong": str(wrong), "right": str(right)})
    return out


def main() -> int:
    from cail_race2.env import load_dotenv
    load_dotenv(os.path.join(ROOT, ".env"))
    ap = argparse.ArgumentParser()
    ap.add_argument("--contracts", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--agg", default=None)
    ap.add_argument("--provider", default="ksxc")
    ap.add_argument("--model", default=None)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    contracts = load_contracts(a.contracts)
    if a.limit:
        contracts = contracts[:a.limit]
    p = load_provider(a.provider)
    client = LLMClient(api_key=p.api_key, base_url=p.base_url,
                       model=a.model or p.model, headers=p.headers, timeout=180)

    def work(c):
        path = os.path.join(a.out, f"{c.contract_id}.json")
        if os.path.exists(path) and not a.force:
            return c.contract_id, json.load(open(path, encoding="utf-8")), True
        try:
            return c.contract_id, annotate(c, client), False
        except Exception as e:
            print("ERR", c.contract_id, type(e).__name__)
            return c.contract_id, [], False

    results = {}
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(work, c): c.contract_id for c in contracts}
        for f in as_completed(futs):
            cid, data, cached = f.result()
            results[cid] = data
            if not cached:
                json.dump(data, open(os.path.join(a.out, f"{cid}.json"), "w", encoding="utf-8"),
                          ensure_ascii=False, indent=1)
            print("%-10s %s 标注 %d 处" % (cid, "缓存" if cached else "完成", len(data)))

    if a.agg:
        os.makedirs(os.path.dirname(a.agg), exist_ok=True)
        with open(a.agg, "w", encoding="utf-8") as f:
            for c in contracts:
                for t in results.get(c.contract_id, []):
                    f.write(json.dumps({"contract_id": c.contract_id, **t}, ensure_ascii=False) + "\n")
        print("汇总:", a.agg)
    total = sum(len(v) for v in results.values())
    print("合同 %d | 标注总数 %d" % (len(results), total))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
