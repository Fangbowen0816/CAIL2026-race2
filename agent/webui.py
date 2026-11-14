# -*- coding: utf-8 -*-
"""极简 WebUI：粘贴合同 → 运行验收链（审查 → MCP 评分）→ 展示交付物与分数。"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, ROOT)

PAGE = """<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<title>合同审查 Agent</title>
<style>body{font-family:system-ui,"Microsoft YaHei";max-width:900px;margin:32px auto;padding:0 16px}
textarea{width:100%;height:260px;font-family:ui-monospace,Consolas,monospace}
input,button{font-size:15px;padding:6px 10px}pre{background:#f4f6fa;padding:12px;overflow:auto}</style>
<h2>合同审查 Agent</h2>
<form id="f">
<p>合同编号 <input name="contract_id" value="WEB-001"></p>
<p><textarea name="context" placeholder='粘贴合同原文（含 &lt;p id="N"&gt; 标签）'></textarea></p>
<button type="submit">审查并评分</button>
</form><pre id="out"></pre>
<script>
document.getElementById('f').onsubmit=async e=>{e.preventDefault();const o=document.getElementById('out');
o.textContent='运行中…';const r=await fetch('/run',{method:'POST',body:new FormData(e.target)});
o.textContent=JSON.stringify(await r.json(),null,2);};
</script></html>"""


def serve(port: int = 8800, model=None):
    from flask import Flask, jsonify, request

    from agent.mcp_client import MCPClient, default_command
    from agent.review import review_contract
    from cail_race2.contracts import Contract, parse_paragraphs

    app = Flask(__name__)

    @app.get("/")
    def index():
        return PAGE

    @app.post("/run")
    def run():
        cid = (request.form.get("contract_id") or "WEB-001").strip()
        context = request.form.get("context") or ""
        contract = Contract(cid, context, parse_paragraphs(context))
        from cli import make_client, MCP_SERVER  # 延迟导入，复用配置
        out_dir = os.path.join(ROOT, "outputs", "webui", cid)
        try:
            client, _ = make_client(model)
            res = review_contract(contract, out_dir, client)
            with MCPClient(default_command(MCP_SERVER)) as mcp:
                mcp.initialize()
                score = json.loads(mcp.call_tool("score_review", {
                    "contract_id": cid, "context": context,
                    "localization": res["localization"], "revision": res["revision"]}))
            return jsonify({"contract_id": cid, "score": score,
                            "annotated": res["annotated"], "report": res["report"]})
        except Exception as e:
            return jsonify({"error": f"{type(e).__name__}: {e}"})

    app.run(host="127.0.0.1", port=port, debug=False)


if __name__ == "__main__":
    serve()
