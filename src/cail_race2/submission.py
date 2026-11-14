# -*- coding: utf-8 -*-
"""提交产物写出：原子写 JSONL + 打包 zip。"""
from __future__ import annotations

import json
import os
import tempfile
import zipfile


def write_jsonl(path: str, rows: list[dict]) -> None:
    """原子写出 JSONL：先写临时文件再 os.replace，避免半写文件。"""
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def make_zip(zip_path: str, file_paths: list[str]) -> str:
    """把若干文件压进 zip，arcname 用文件名（包内扁平放置）。"""
    os.makedirs(os.path.dirname(os.path.abspath(zip_path)), exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in file_paths:
            z.write(p, arcname=os.path.basename(p))
    return zip_path
