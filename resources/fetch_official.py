# -*- coding: utf-8 -*-
"""拉取 CAIL 2026 官网公开信息到本地 resources/official/2026/。

只调用公开接口（无需登录）；数据集/下载链接需要赛事账号，登录态才能取。
用法：python resources/fetch_official.py
"""
import json
import os
import urllib.request

BASE = "http://cail.cipsc.org.cn/api"
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "official", "2026")

RACES = {
    2: "race2_contract_review",
    3: "race3_online_infringement",
}


def post(ep, body):
    req = urllib.request.Request(
        BASE + ep,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:  # noqa
        return {"__error__": str(e)}


def save(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    return path


def save_text(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text or "")
    return path


def main():
    # 全局通知
    notices = post("/querynotice", {})
    save(os.path.join(ROOT, "notices_global.json"), notices)

    for rid, slug in RACES.items():
        d = os.path.join(ROOT, slug)
        print("== race", rid, d)

        info = post("/taskInfo", {"raceID": rid, "cail_tag": "2026", "step": 0})
        save(os.path.join(d, "taskInfo.json"), info)

        race = post("/getRaceInfo", {"raceID": rid, "cail_tag": "2026"})
        save(os.path.join(d, "raceInfo.json"), race)
        data = (race or {}).get("data") or {}
        for key, fn in [("detail", "detail.md"), ("join", "join.md"),
                        ("timeline", "timeline.md"), ("reward", "reward.md")]:
            node = data.get(key) or {}
            save_text(os.path.join(d, fn), node.get("content", ""))

        save(os.path.join(d, "stageName.json"),
             post("/getStageName", {"raceID": rid, "cail_tag": "2026"}))
        save(os.path.join(d, "stageInfo.json"),
             post("/getStageInfo", {"raceID": rid, "cail_tag": "2026"}))
        save(os.path.join(d, "timePeriod.json"),
             post("/getTimePeriod", {"raceID": rid, "cail_tag": "2026"}))
        save(os.path.join(d, "prizeList.json"),
             post("/getPrizeList", {"raceID": rid, "cail_tag": "2026"}))
        save(os.path.join(d, "notices.json"),
             post("/queryRaceNotice", {"raceID": rid, "cail_tag": "2026"}))
        # 需登录的接口，记录返回以便知道缺口
        save(os.path.join(d, "datasetList.json"),
             post("/getDatasetList", {"race_id": rid, "cail_tag": "2026", "user_id": ""}))

    # 站点四赛道总览（来自站点前端静态数据 jse）
    site = {
        "version": "2026",
        "races": [
            {"raceID": 0, "title": "智能律师实务", "kind": "国内赛道 · 01",
             "subtitle": "案件研判与法律意见生成",
             "desc": "面向律师真实工作流程，考查阅卷与争议识别、证据组织与审查、法律检索与适用、案件策略研判、法律文书与释法说理、司法程序与客户服务六类能力。"},
            {"raceID": 1, "title": "刑事法律推理", "kind": "国内赛道 · 02",
             "subtitle": "定罪判断与出罪路径识别",
             "desc": "面向中国刑事司法场景，基于三阶层犯罪论进行层级推理：先判断犯罪是否成立，成立则识别具体罪名，不成立则识别 doctrine 与具体出罪类型。"},
            {"raceID": 2, "title": "智能合同审查", "kind": "国内赛道 · 03",
             "subtitle": "错误定位与条款修改",
             "desc": "面向智能合同审查，含错误定位与分类、合同条款修改两个子任务。"},
            {"raceID": 3, "title": "涉网侵权治理", "kind": "国内赛道 · 04",
             "subtitle": "事实认定、责任划分与治理决策",
             "desc": "面向网络平台内容治理、网信监管、检察公益诉讼与网络侵权诉讼场景，对涉网侵权内容进行事实认定与责任划分，并生成处置措施与治理决策建议。"},
        ],
        "source": "http://cail.cipsc.org.cn/ 前端静态数据 (assets/index-*.js) + /api 接口",
    }
    save(os.path.join(ROOT, "site_overview.json"), site)
    print("done ->", ROOT)


if __name__ == "__main__":
    main()
