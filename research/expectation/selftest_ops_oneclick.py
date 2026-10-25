#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一键任务运维小版（v0.72）selftest：完成标记幂等 + 上传前硬校验。
运行：python research/expectation/selftest_ops_oneclick.py
"""
import datetime
import importlib.util
import io
import json
import os
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

_p = 0
_f = 0


def ok(name, cond):
    global _p, _f
    if cond:
        _p += 1
        print("PASS %s" % name)
    else:
        _f += 1
        print("FAIL %s" % name)


def _load(mod_name):
    spec = importlib.util.spec_from_file_location(mod_name, os.path.join(_HERE, mod_name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ac = _load("run_one_click_after_close")
pm = _load("run_one_click_premarket")

ok("T1 版本号 v0.72(收盘)", ac.SCRIPT_VERSION == "v0.72")
ok("T1 版本号 v0.72(盘前)", pm.SCRIPT_VERSION == "v0.72")

# --- T2 完成标记：幂等跳过（复盘任务链已跑过）---
tmp = tempfile.mkdtemp(prefix="pt_ops_")
ok("T2 无标记不跳过", ac._skip_if_done(tmp, "2026-10-26", True) is False)
ac._write_done_marker(tmp, "2026-10-26", "2026-10-27", {"k": "v"})
ok("T2 有标记则跳过", ac._skip_if_done(tmp, "2026-10-26", True) is True)
ok("T2 未开启时不跳过", ac._skip_if_done(tmp, "2026-10-26", False) is False)
_mk = json.load(io.open(ac._marker_path(tmp, "2026-10-26"), encoding="utf-8"))
ok("T2 标记字段齐备", _mk.get("version") == "v0.72" and _mk.get("next_trade_date") == "2026-10-27"
   and bool(_mk.get("generated_at")) and _mk.get("files") == {"k": "v"})
ok("T2 日期不同不跳过", ac._skip_if_done(tmp, "2026-10-27", True) is False)


# --- T3 单文件硬校验：存在 + 行数>0 + date 对齐 ---
def _w(path, text):
    with io.open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


d = tempfile.mkdtemp(prefix="pt_ops_csv_")
fp = os.path.join(d, "zt_lianban_latest.csv")
ok("T3 文件缺失 -> FAIL", pm._check_upload_file("zt", fp, "2026-10-23")[0] == 1)
_w(fp, "date,code\n")
ok("T3 空表 -> FAIL", pm._check_upload_file("zt", fp, "2026-10-23")[0] == 1)
_w(fp, "date,code\n2026-10-22,X\n")
ok("T3 date 不符 -> FAIL", pm._check_upload_file("zt", fp, "2026-10-23")[0] == 1)
_w(fp, "date,code\n2026-10-23,X\n2026-10-23,Y\n")
_bad, _msg = pm._check_upload_file("zt", fp, "2026-10-23")
ok("T3 date 一致且有行 -> OK", _bad == 0 and "rows=2" in _msg)


# --- T4 预期 CSV vs archive meta：row_count/sha1 硬校验 ---
def _case(rows_text, meta):
    _d = tempfile.mkdtemp(prefix="pt_ops_exp_")
    _csv = os.path.join(_d, "expectation_latest.csv")
    _meta = os.path.join(_d, "expectation_2026-10-26.csv.meta.json")
    _w(_csv, rows_text)
    if meta is not None:
        with io.open(_meta, "w", encoding="utf-8", newline="") as f:
            json.dump(meta, f)
    return pm._check_expectation_meta(_csv, _meta)


_hdr = "code,name,side\n"
_body2 = _hdr + "600838.XSHG,A,buy\n600000.XSHG,B,buy\n"
ok("T4 无 meta 仅行数校验 -> OK", _case(_body2, None)[0] == 0)
ok("T4 行数不一致 -> FAIL", _case(_body2, {"row_count": 1, "sha1": ""})[0] == 1)


def _case_sha(text, bad_sha=False):
    _d = tempfile.mkdtemp(prefix="pt_ops_exp2_")
    _csv = os.path.join(_d, "expectation_latest.csv")
    _meta = os.path.join(_d, "expectation_2026-10-26.csv.meta.json")
    _w(_csv, text)
    _sha = pm._sha1_of(_csv)
    with io.open(_meta, "w", encoding="utf-8", newline="") as f:
        json.dump({"row_count": 2, "sha1": ("0" * 40) if bad_sha else _sha}, f)
    return pm._check_expectation_meta(_csv, _meta)


ok("T4 sha1 一致 -> OK", _case_sha(_body2)[0] == 0)
ok("T4 sha1 不一致 -> FAIL(疑似被覆盖)", _case_sha(_body2, bad_sha=True)[0] == 1)
ok("T4 空表 -> FAIL", _case(_hdr, {"row_count": 0, "sha1": "x"})[0] == 1)

# --- T5 文案对齐：09:15 为上传截止，不再出现 09:20 ---
_src = io.open(os.path.join(_HERE, "run_one_click_premarket.py"), encoding="utf-8").read()
ok("T5 盘前文案含 09:15", "09:15" in _src and "09:20" not in _src)
_cs = io.open(os.path.join(_HERE, "run_one_click_after_close.py"), encoding="utf-8").read()
ok("T5 收盘文案含 --skip-if-done", "--skip-if-done" in _cs)


# --- T6 非交易日兜底不跑（无 --date 时）---
import types


class _FakeDate(datetime.date):
    @classmethod
    def today(cls):
        return cls(2026, 10, 25)   # 周日


_orig_dt = ac.datetime
ac.datetime = types.SimpleNamespace(date=_FakeDate, datetime=datetime.datetime)
try:
    _rc = ac.main([])
finally:
    ac.datetime = _orig_dt
ok("T6 非交易日 -> rc=0 跳过", _rc == 0)

print("TOTAL pass=%d fail=%d" % (_p, _f))
raise SystemExit(1 if _f else 0)
