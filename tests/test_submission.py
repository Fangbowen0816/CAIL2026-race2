# -*- coding: utf-8 -*-
import json
import os
import zipfile

from cail_race2.submission import make_zip, write_jsonl


def test_write_jsonl_round_trip_utf8(tmp_path):
    p = tmp_path / "out.jsonl"
    rows = [{"contract_id": "C1", "text": "错别字"}, {"contract_id": "C2", "text": "a"}]
    write_jsonl(str(p), rows)
    got = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()]
    assert got == rows


def test_write_jsonl_leaves_no_tmp_file(tmp_path):
    p = tmp_path / "out.jsonl"
    write_jsonl(str(p), [{"a": 1}])
    assert [f for f in os.listdir(tmp_path) if f.endswith(".tmp")] == []


def test_make_zip_contains_both_files(tmp_path):
    f1 = tmp_path / "localization_predictions.jsonl"
    f2 = tmp_path / "revision_predictions.jsonl"
    write_jsonl(str(f1), [{"a": 1}])
    write_jsonl(str(f2), [{"b": 2}])
    z = make_zip(str(tmp_path / "sub.zip"), [str(f1), str(f2)])
    with zipfile.ZipFile(z) as zf:
        assert set(zf.namelist()) == {"localization_predictions.jsonl",
                                      "revision_predictions.jsonl"}
