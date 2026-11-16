# -*- coding: utf-8 -*-
"""用模型穷举标注合同错误（missing / stance / inconsistency），用作**召回验证集**。

该集仅用于评估召回，agent 不查询；含合同文本片段，故输出目录已 gitignore。

用法：
  python scripts/annotate_errors.py --kind stance \
      --contracts resources/datasets/race2_semifinal/data/contracts.jsonl \
      --out resources/recall/annot_stance --provider ksxc --model glm-5.3-flash --workers 8
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

from agent.config import load_provider          # noqa: E402
from cail_race2.contracts import load_contracts  # noqa: E402
from cail_race2.llm import LLMClient             # noqa: E402

SYS = {
    "missing": """你是资深合同审查专家。任务：逐段找出合同中**要素缺失**的条款。

判定：合同已就某事项作出约定，但**缺少必要信息**，导致权利义务无法确定。例如：
已约定交付却未写交付时间/地点；已约定付款却未写付款期限/方式/账户；
已约定违约金却未写计算方式；主体信息不全；"另行协商""另行约定""待定"等占位表述（解读为缺漏）。
**不要报**：信息完整、只是表述简略的条款；非本条必需的商业条款。

严格只输出 JSON：{"errors":[{"pid":段落号整数,"reason":"缺什么"}]}；无则 {"errors":[]}。""",
    "stance": """你是资深合同审查专家。任务：逐条找出**立场失衡（显失公平/权利义务明显不对等）**的条款。

判据（命中任一即算）：
A 履行顺序/担保：要求一方先履行且对方无对等保障；B 责任免除：免除一方责任、限制对方主要权利；
C 单方/无条件/无限期：一方可单方、无条件、无限期作为；D 风险/费用单向转嫁（含无过错担责、"无偿""全部费用由X承担"）；
E 救济缺失：只约束一方、不给整改/救济机会。
**注意隐蔽形态**：名为"同时履行"实为一方先付；表面双向实则只罚一方；
**不要报**：对等、合理、给了合理期限或补救机会的条款；占位符/缺漏条款（那是要素缺失）。

严格只输出 JSON：{"errors":[{"pid":段落号整数,"reason":"简述失衡点"}]}；无则 {"errors":[]}。""",
    "inconsistency": """你是资深合同审查专家。任务：找出**跨段（上下文）不一致**的问题。

判定：同一事项在不同段落表述矛盾/冲突，例如：当事人名称前后不同、金额/单价×数量≠总价、
期限/比例/性质前后不一致、条款编号引用错位、标的名称不统一。
**必须列出全部冲突段号**（不能只报一侧）。**不要报**：单段内部的文字错误；彼此不冲突的表述。

严格只输出 JSON：{"errors":[{"pids":[段号,...],"reason":"冲突点"}]}；无则 {"errors":[]}。""",
}


def _msgs(contract, kind):
    lines = [f"p{pid}: {t}" for pid, t in sorted(contract.paragraphs.items()) if (t or "").strip()]
    return [{"role": "system", "content": SYS[kind]},
            {"role": "user", "content": "逐段分析以下合同：\n" + "\n".join(lines)}]


def annotate(contract, client, kind):
    obj = client.complete_json(_msgs(contract, kind), temperature=0.0)
    items = obj.get("errors") if isinstance(obj, dict) else None
    out = []
    for it in (items or []):
        if not isinstance(it, dict):
            continue
        pids = it.get("pids") or ([it["pid"]] if isinstance(it.get("pid"), int) else [])
        pids = [p for p in pids if isinstance(p, int) and p in contract.paragraphs]
        if pids:
            out.append({"pids": sorted(set(pids)), "reason": str(it.get("reason") or "")[:120]})
    return out


def main() -> int:
    from cail_race2.env import load_dotenv
    load_dotenv(os.path.join(ROOT, ".env"))
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", required=True, choices=list(SYS))
    ap.add_argument("--contracts", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--provider", default="ksxc")
    ap.add_argument("--model", default=None)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    p = load_provider(a.provider)
    client = LLMClient(api_key=p.api_key, base_url=p.base_url,
                       model=a.model or p.model, headers=p.headers, timeout=200)
    contracts = load_contracts(a.contracts)

    def work(c):
        path = os.path.join(a.out, f"{c.contract_id}.json")
        if os.path.exists(path) and not a.force:
            return c.contract_id, json.load(open(path, encoding="utf-8")), True
        try:
            return c.contract_id, annotate(c, client, a.kind), False
        except Exception as e:
            print("ERR", c.contract_id, type(e).__name__)
            return c.contract_id, [], False

    res = {}
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        for f in as_completed({ex.submit(work, c): c.contract_id for c in contracts}):
            cid, data, cached = f.result()
            res[cid] = data
            if not cached:
                json.dump(data, open(os.path.join(a.out, f"{cid}.json"), "w", encoding="utf-8"),
                          ensure_ascii=False)
            print("%-10s %s %d" % (cid, "缓存" if cached else "完成", len(data)))
    print("%s 标注总数 %d" % (a.kind, sum(len(v) for v in res.values())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
