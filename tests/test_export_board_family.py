# -*- coding: utf-8 -*-
"""v1.42 家族映射导出：人工 override + 全量概念成员 + 近10日题材桶回归测试。"""
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPORT_PATH = ROOT / "research" / "expectation" / "export_board_family.py"


def _load_export():
    sys.path.insert(0, str(EXPORT_PATH.parent))
    spec = importlib.util.spec_from_file_location("export_board_family_test", EXPORT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write_manual(tmp_path, payload):
    fp = tmp_path / "board_family_override.json"
    fp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return fp


def _write_ths(tmp_path, concept_members):
    # concept_members: {board_name: [codes]}，生成 AXquant ths_board_mapping.json 长格式
    rows = []
    for board, codes in concept_members.items():
        for code in codes:
            rows.append({"code": code, "board_name": board, "board_type": "concept", "board_rank": 1})
    fp = tmp_path / "ths_board_mapping.json"
    fp.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return fp


def _write_analysis(tmp_path, date, buckets):
    # buckets: {bucket_name: [codes]}，生成 review_analysis_<date>.json 题材桶片段
    fp = tmp_path / ("review_analysis_%s.json" % date)
    payload = {"theme": {"buckets": {name: {"codes": codes} for name, codes in buckets.items()}}}
    fp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return fp


def _run(tmp_path, manual=None, ths=None, analyses=None, min_overlap=2):
    mod = _load_export()
    out = tmp_path / "out"
    out.mkdir(exist_ok=True)
    analysis_dir = tmp_path / "analysis"
    analysis_dir.mkdir(exist_ok=True)
    for date, buckets in (analyses or []):
        _write_analysis(analysis_dir, date, buckets)
    args = {
        "mapping_path": str(_write_manual(tmp_path, manual or {})),
        "out_dir": str(out),
        "ths_mapping_path": str(_write_ths(tmp_path, ths or {})),
        "analysis_dir": str(analysis_dir),
        "min_overlap": min_overlap,
    }
    res = mod.run(**args)
    return res, out


def _csv_rows(out):
    lines = (out / "board_family_latest.csv").read_text(encoding="utf-8").splitlines()
    assert lines[0] == "board_name,family_name"
    return {b: f for b, f in (line.split(",", 1) for line in lines[1:] if line)}


def test_auto_mapping_from_latest_bucket(tmp_path):
    res, out = _run(
        tmp_path,
        manual={"黄金概念": "黄金/有色/资源"},
        ths={
            "黄金概念": ["G1.SZ", "G2.SZ", "G3.SZ"],
            "光伏概念": ["P1.SH", "P2.SH", "P3.SH"],
        },
        analyses=[("2026-11-05", {"黄金/有色/资源": ["G1.SZ", "G2.SZ"], "光伏/风电": ["P1.SH", "P2.SH"]})],
    )
    assert res["status"] == "WROTE"
    assert res["rows"] == 2
    assert res["manual_rows"] == 1
    assert res["auto_boards"] == 2
    rows = _csv_rows(out)
    assert rows["黄金概念"] == "黄金/有色/资源"
    assert rows["光伏概念"] == "光伏/风电"


def test_manual_wins_over_auto(tmp_path):
    _, out = _run(
        tmp_path,
        manual={"光伏概念": "人工族"},
        ths={"光伏概念": ["P1.SH", "P2.SH"]},
        analyses=[("2026-11-05", {"光伏/风电": ["P1.SH", "P2.SH"]})],
    )
    rows = _csv_rows(out)
    assert rows["光伏概念"] == "人工族"


def test_latest_day_preferred_over_historical(tmp_path):
    _, out = _run(
        tmp_path,
        manual={"黄金概念": "黄金/有色/资源"},
        ths={"芯片概念": ["C1.SZ", "C2.SZ", "C3.SZ"]},
        analyses=[
            ("2026-11-05", {"最新族": ["C1.SZ", "C2.SZ"]}),
            ("2026-11-04", {"历史族": ["C1.SZ", "C2.SZ", "C3.SZ"]}),
        ],
    )
    rows = _csv_rows(out)
    assert rows["芯片概念"] == "最新族"


def test_min_overlap_filter(tmp_path):
    _, out = _run(
        tmp_path,
        manual={"黄金概念": "黄金/有色/资源"},
        ths={"边缘概念": ["E1.SZ", "E2.SZ"]},
        analyses=[("2026-11-05", {"某族": ["E1.SZ"]})],
    )
    assert "边缘概念" not in _csv_rows(out)
    _, out2 = _run(
        tmp_path,
        manual={"黄金概念": "黄金/有色/资源"},
        ths={"边缘概念": ["E1.SZ", "E2.SZ"]},
        analyses=[("2026-11-05", {"某族": ["E1.SZ"]})],
        min_overlap=1,
    )
    assert _csv_rows(out2)["边缘概念"] == "某族"


def test_historical_cumulative_fallback(tmp_path):
    _, out = _run(
        tmp_path,
        manual={"黄金概念": "黄金/有色/资源"},
        ths={"边缘概念": ["E1.SZ", "E2.SZ"]},
        analyses=[
            ("2026-11-05", {"无关系": ["X1.SH"]}),
            ("2026-11-04", {"历史族": ["E1.SZ"]}),
            ("2026-11-03", {"历史族": ["E2.SZ"]}),
        ],
    )
    rows = _csv_rows(out)
    assert rows["边缘概念"] == "历史族"


def test_export_board_family_unchanged_keeps_mtime(tmp_path):
    mod = _load_export()
    out = tmp_path / "out"
    out.mkdir()
    analysis_dir = tmp_path / "analysis"
    analysis_dir.mkdir()
    args = {
        "mapping_path": str(_write_manual(tmp_path, {"黄金概念": "黄金/有色/资源"})),
        "out_dir": str(out),
        "ths_mapping_path": str(_write_ths(tmp_path, {"黄金概念": ["G1.SZ", "G2.SZ"]})),
        "analysis_dir": str(analysis_dir),
    }
    assert mod.run(**args)["status"] == "WROTE"
    fp = out / "board_family_latest.csv"
    mtime1 = fp.stat().st_mtime
    res = mod.run(**args)
    assert res["status"] == "UNCHANGED"
    assert fp.stat().st_mtime == mtime1


def test_missing_analysis_manual_only(tmp_path):
    res, out = _run(
        tmp_path,
        manual={"黄金概念": "黄金/有色/资源", "稀土永磁": "黄金/有色/资源"},
        ths={"黄金概念": ["G1.SZ", "G2.SZ"]},
    )
    assert res["status"] == "WROTE"
    assert res["rows"] == 2
    assert res["auto_boards"] == 0


def test_missing_manual_keeps_old(tmp_path):
    mod = _load_export()
    out = tmp_path / "out"
    out.mkdir()
    analysis_dir = tmp_path / "analysis"
    analysis_dir.mkdir()
    src = _write_manual(tmp_path, {"黄金概念": "黄金/有色/资源"})
    ths = _write_ths(tmp_path, {"黄金概念": ["G1.SZ", "G2.SZ"]})
    args = {"mapping_path": str(src), "out_dir": str(out), "ths_mapping_path": str(ths), "analysis_dir": str(analysis_dir)}
    assert mod.run(**args)["status"] == "WROTE"
    fp = out / "board_family_latest.csv"
    old = fp.read_text(encoding="utf-8")
    res = mod.run(mapping_path=str(tmp_path / "nope.json"), out_dir=str(out),
                  ths_mapping_path=str(ths), analysis_dir=str(analysis_dir))
    assert res["status"] == "MISSING_SOURCE"
    assert fp.read_text(encoding="utf-8") == old


def test_invalid_manual_keeps_old(tmp_path):
    mod = _load_export()
    out = tmp_path / "out"
    out.mkdir()
    analysis_dir = tmp_path / "analysis"
    analysis_dir.mkdir()
    src = _write_manual(tmp_path, {"黄金概念": "黄金/有色/资源"})
    ths = _write_ths(tmp_path, {"黄金概念": ["G1.SZ", "G2.SZ"]})
    args = {"mapping_path": str(src), "out_dir": str(out), "ths_mapping_path": str(ths), "analysis_dir": str(analysis_dir)}
    assert mod.run(**args)["status"] == "WROTE"
    fp = out / "board_family_latest.csv"
    old = fp.read_text(encoding="utf-8")
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    res = mod.run(mapping_path=str(bad), out_dir=str(out),
                  ths_mapping_path=str(ths), analysis_dir=str(analysis_dir))
    assert res["status"] == "INVALID_SOURCE"
    assert fp.read_text(encoding="utf-8") == old


def test_missing_ths_keeps_old(tmp_path):
    mod = _load_export()
    out = tmp_path / "out"
    out.mkdir()
    analysis_dir = tmp_path / "analysis"
    analysis_dir.mkdir()
    src = _write_manual(tmp_path, {"黄金概念": "黄金/有色/资源"})
    ths = _write_ths(tmp_path, {"黄金概念": ["G1.SZ", "G2.SZ"]})
    args = {"mapping_path": str(src), "out_dir": str(out), "ths_mapping_path": str(ths), "analysis_dir": str(analysis_dir)}
    assert mod.run(**args)["status"] == "WROTE"
    fp = out / "board_family_latest.csv"
    old = fp.read_text(encoding="utf-8")
    res = mod.run(mapping_path=str(src), out_dir=str(out),
                  ths_mapping_path=str(tmp_path / "nope.json"), analysis_dir=str(analysis_dir))
    assert res["status"] == "MISSING_SOURCE"
    assert fp.read_text(encoding="utf-8") == old


def test_invalid_ths_keeps_old(tmp_path):
    mod = _load_export()
    out = tmp_path / "out"
    out.mkdir()
    analysis_dir = tmp_path / "analysis"
    analysis_dir.mkdir()
    src = _write_manual(tmp_path, {"黄金概念": "黄金/有色/资源"})
    ths = _write_ths(tmp_path, {"黄金概念": ["G1.SZ", "G2.SZ"]})
    args = {"mapping_path": str(src), "out_dir": str(out), "ths_mapping_path": str(ths), "analysis_dir": str(analysis_dir)}
    assert mod.run(**args)["status"] == "WROTE"
    fp = out / "board_family_latest.csv"
    old = fp.read_text(encoding="utf-8")
    bad = tmp_path / "bad_ths.json"
    bad.write_text("{not json", encoding="utf-8")
    res = mod.run(mapping_path=str(src), out_dir=str(out),
                  ths_mapping_path=str(bad), analysis_dir=str(analysis_dir))
    assert res["status"] == "INVALID_SOURCE"
    assert fp.read_text(encoding="utf-8") == old
