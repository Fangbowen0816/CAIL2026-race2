# -*- coding: utf-8 -*-
"""CAIL 2026 数据集下载助手（需赛事账号登录态）。

登录态二选一（均通过环境变量注入，不落盘）：
  1) 已有浏览器 Cookie：    set CAIL_COOKIE="<浏览器复制的一整串 Cookie>"
  2) 手机号 + 短信验证码：  set CAIL_PHONE=1xxxxxxxxxx   set CAIL_CODE=123456

用法：
  python resources/download_dataset.py --race 2 --out resources/datasets/race2_contract_review

说明：先调用 /getDatasetList 列出数据集，再逐个调用 /get_download_url 下载并保存。
若接口字段与预期不同，会原样打印 JSON 供排查。
"""
import argparse
import json
import os
import re
import sys
import urllib.request
from http.cookiejar import CookieJar

BASE = "http://cail.cipsc.org.cn/api"


def make_opener(cookie_str=None):
    jar = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    opener.addheaders = [("X-Requested-With", "XMLHttpRequest"),
                         ("Accept", "application/json")]
    if cookie_str:
        opener.addheaders.append(("Cookie", cookie_str))
    return opener


def post(opener, ep, body):
    req = urllib.request.Request(
        BASE + ep, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with opener.open(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def login_by_code(opener, phone, code):
    r = post(opener, "/login", {"userID": phone, "password": code})
    print("login ->", json.dumps(r, ensure_ascii=False)[:300])
    return r


def deep_urls(obj, acc):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and re.match(r"^https?://", v):
                acc.append((k, v))
            else:
                deep_urls(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            deep_urls(v, acc)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--race", type=int, required=True)
    ap.add_argument("--tag", default="2026")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    opener = make_opener(os.environ.get("CAIL_COOKIE"))
    if not os.environ.get("CAIL_COOKIE") and os.environ.get("CAIL_PHONE"):
        login_by_code(opener, os.environ["CAIL_PHONE"], os.environ.get("CAIL_CODE", ""))

    user = os.environ.get("CAIL_PHONE", "")
    lst = post(opener, "/getDatasetList",
               {"race_id": a.race, "cail_tag": a.tag, "user_id": user})
    print("=== getDatasetList ===")
    print(json.dumps(lst, ensure_ascii=False, indent=2)[:4000])

    rows = ((lst or {}).get("data") or {}).get("rows") or []
    os.makedirs(a.out, exist_ok=True)
    for row in rows:
        did = row.get("id") or row.get("dataset_id") or row.get("datasetId")
        if did is None:
            continue
        got = post(opener, "/get_download_url",
                   {"raceID": a.race, "cail_tag": a.tag, "userID": user, "dataset_id": did})
        print("download_url(%s) ->" % did, json.dumps(got, ensure_ascii=False)[:400])
        urls = []
        deep_urls(got, urls)
        for name, url in urls:
            fn = os.path.join(a.out, os.path.basename(url.split("?")[0]) or ("dataset_%s" % did))
            try:
                urllib.request.urlretrieve(url, fn)
                print("  saved", fn, os.path.getsize(fn))
            except Exception as e:  # noqa
                print("  FAIL", url, e)


if __name__ == "__main__":
    sys.exit(main())
