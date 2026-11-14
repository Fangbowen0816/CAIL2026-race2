# -*- coding: utf-8 -*-
"""统一 CLI：把 Agent / Skill / MCP 串起来。

  python cli.py review   --contract <file> --out <dir> [--dry]     # 只审查
  python cli.py agent    --contract <file> --out <dir>             # LLM Agent 自主跑链
  python cli.py accept   --contract <file> --out <dir>             # 验收链：审查→MCP评分→交付
  python cli.py benchmark [--contracts <jsonl>] --out <dir>        # 批量跑 CAIL 基准并打包
  python cli.py webui    [--port 8800]                             # 网页入口
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, ROOT)

DEFAULT_CONTRACTS = os.path.join(
    ROOT, "resources", "datasets", "race2_contract_review", "contracts.jsonl")
MCP_SERVER = os.path.join(ROOT, "mcp_eval", "server.py")
SKILLS_DIR = os.path.join(ROOT, "skills")


def make_client(model=None):
    from agent.config import load_ksxc_provider
    from cail_race2.llm import LLMClient
    p = load_ksxc_provider()
    return LLMClient(base_url=p.base_url, model=model or p.model,
                     headers=p.headers, api_key=p.api_key, json_mode=False), p


def _contract_text(path: str) -> dict:
    if path.endswith(".jsonl"):
        return json.loads(open(path, encoding="utf-8").readline())
    return json.load(open(path, encoding="utf-8"))


def cmd_review(a):
    from agent.review import _load_one, review_contract
    client = None if a.dry else make_client(a.model)[0]
    res = review_contract(_load_one(a.contract), a.out, client, dry=a.dry)
    print(json.dumps({k: res[k] for k in ("contract_id", "annotated", "report")},
                     ensure_ascii=False, indent=2))


def cmd_accept(a):
    from agent.mcp_client import MCPClient, default_command
    from agent.review import _load_one, review_contract
    client, prov = make_client(a.model)
    c = _load_one(a.contract)
    res = review_contract(c, a.out, client)
    with MCPClient(default_command(MCP_SERVER)) as mcp:
        mcp.initialize()
        score = json.loads(mcp.call_tool("score_review", {
            "contract_id": c.contract_id, "context": c.context,
            "localization": res["localization"], "revision": res["revision"]}))
    print(f"provider: {prov.redacted()}")
    print("交付物：")
    print("  -", res["annotated"])
    print("  -", res["report"])
    print("  -", os.path.join(a.out, "localization_predictions.jsonl"),
          "/", os.path.join(a.out, "revision_predictions.jsonl"))
    print("MCP 评测：", json.dumps(score, ensure_ascii=False))


def cmd_agent(a):
    import json as _json
    from agent.loop import Agent
    from agent.mcp_client import MCPClient, default_command
    from agent.review import _load_one, review_contract as _review
    from agent.skills import SkillCatalog
    from agent.tools import Workspace

    client, prov = make_client(a.model)

    def tool_review_contract(contract, out):
        c = _load_one(os.path.join(ROOT, contract) if not os.path.isabs(contract) else contract)
        res = _review(c, out, client)
        return "已审查并写出：annotated.md / report.md / localization_predictions.jsonl / revision_predictions.jsonl 到 " + out

    def tool_load_review(contract, out):
        c = _load_one(os.path.join(ROOT, contract) if not os.path.isabs(contract) else contract)
        outa = os.path.join(ROOT, out) if not os.path.isabs(out) else out
        loc = [json.loads(l) for l in open(os.path.join(outa, "localization_predictions.jsonl"), encoding="utf-8") if l.strip()]
        rev = [json.loads(l) for l in open(os.path.join(outa, "revision_predictions.jsonl"), encoding="utf-8") if l.strip()]
        return _json.dumps({"contract_id": c.contract_id, "context": c.context,
                            "localization": loc, "revision": rev}, ensure_ascii=False)

    def _schema(name, desc):
        props = {"contract": {"type": "string"}, "out": {"type": "string"}}
        return {"type": "function", "function": {
            "name": name, "description": desc,
            "parameters": {"type": "object", "properties": props,
                           "required": ["contract", "out"]}}}

    extra = {
        "review_contract": (tool_review_contract,
                            _schema("review_contract", "按 contract-review 技能审查合同并写出交付物")),
        "load_review": (tool_load_review,
                        _schema("load_review", "读取已生成的审查结果，返回 score_review 所需的完整入参 JSON")),
    }

    cat = SkillCatalog(SKILLS_DIR)
    system = ("你是合同审查 Agent。可用工具：review_contract / load_review / MCP 评测工具，"
              "以及 read_file / write_file / list_dir / run_shell。\n技能目录：\n"
              + cat.catalog_text() + "\n"
              "必须严格按以下步骤执行，禁止探索代码库或自行写脚本：\n"
              "1) 调用 review_contract(contract, out)；\n"
              "2) 调用 load_review(contract, out) 得到入参 JSON；\n"
              "3) 用该 JSON 的四个字段调用 MCP 工具 score_review；\n"
              "4) 用简洁中文汇报交付文件路径与评测分数。")
    task = (f"审查合同：{a.contract}，输出目录：{a.out}。"
            f"严格按系统消息的 1→2→3→4 步执行。")
    with MCPClient(default_command(MCP_SERVER)) as mcp:
        mcp.initialize()
        agent = Agent(client, Workspace(ROOT), mcp, max_steps=12, extra_tools=extra)
        out = agent.run(system, task)
    print(f"provider: {prov.redacted()}")
    print("最终答复：\n" + out["answer"])
    print("工具调用轨迹：")
    for t in out["trace"]:
        print(f"  step{t['step']} {t['tool']} {json.dumps(t['args'], ensure_ascii=False)[:100]}")


def cmd_benchmark(a):
    from cail_race2.pipeline import run_staged
    from cail_race2.submission import make_zip
    client, prov = make_client(a.model)
    print("provider:", prov.redacted())
    stats = run_staged(a.contracts, a.out, client, force=a.force, progress=print)
    zip_path = make_zip(os.path.join(a.out, "cail2026_race2_submission.zip"),
                        [os.path.join(a.out, "localization_predictions.jsonl"),
                         os.path.join(a.out, "revision_predictions.jsonl")])
    print(f"完成：合同 {stats.contracts}，定位 {stats.localizations}，修订 {stats.revisions}")
    print("提交包:", zip_path)


def cmd_webui(a):
    from agent import webui
    webui.serve(port=a.port, model=a.model)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=None)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("review"); p.add_argument("--contract", required=True); \
        p.add_argument("--out", required=True); p.add_argument("--dry", action="store_true")
    p.set_defaults(fn=cmd_review)

    p = sub.add_parser("accept"); p.add_argument("--contract", required=True); \
        p.add_argument("--out", required=True); p.set_defaults(fn=cmd_accept)

    p = sub.add_parser("agent"); p.add_argument("--contract", required=True); \
        p.add_argument("--out", required=True); p.set_defaults(fn=cmd_agent)

    p = sub.add_parser("benchmark"); p.add_argument("--contracts", default=DEFAULT_CONTRACTS); \
        p.add_argument("--out", default=os.path.join(ROOT, "outputs", "agent_bench")) ; \
        p.add_argument("--force", action="store_true"); p.set_defaults(fn=cmd_benchmark)

    p = sub.add_parser("webui"); p.add_argument("--port", type=int, default=8800); \
        p.set_defaults(fn=cmd_webui)

    a = ap.parse_args()
    return a.fn(a) or 0


if __name__ == "__main__":
    raise SystemExit(main())
