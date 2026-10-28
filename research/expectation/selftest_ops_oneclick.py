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

ok("T1 版本号 v0.72c(收盘)", ac.SCRIPT_VERSION == "v0.72b")
ok("T1 版本号 v0.72c(盘前)", pm.SCRIPT_VERSION == "v0.72c")

# --- T2 完成标记：幂等跳过（复盘任务链已跑过）---
tmp = tempfile.mkdtemp(prefix="pt_ops_")
ok("T2 无标记不跳过", ac._skip_if_done(tmp, "2026-10-26", True) is False)
ac._write_done_marker(tmp, "2026-10-26", "2026-10-27", {"k": "v"})
ok("T2 有标记则跳过", ac._skip_if_done(tmp, "2026-10-26", True) is True)
ok("T2 未开启时不跳过", ac._skip_if_done(tmp, "2026-10-26", False) is False)
_mk = json.load(io.open(ac._marker_path(tmp, "2026-10-26"), encoding="utf-8"))
ok("T2 标记字段齐备", _mk.get("version") == ac.SCRIPT_VERSION and _mk.get("next_trade_date") == "2026-10-27"
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


# --- T7 dated 文件已归档：不误报为缺失 ---
_d7 = tempfile.mkdtemp(prefix="pt_ops_arc_")
os.makedirs(os.path.join(_d7, "archive"), exist_ok=True)
_f7 = os.path.join(_d7, "expectation_2026-10-26.csv")
ok("T7 无根文件且无归档 -> 空", pm._archived_note(_f7, _d7) == "")
_w(os.path.join(_d7, "archive", "expectation_2026-10-26.csv"), "code,name\n600838.XSHG,A\n")
ok("T7 已归档 -> 提示仅上传 latest", "已归档" in pm._archived_note(_f7, _d7))

# --- T8 板块映射周更（v0.72c，周一固定）+ run 幂等 ---
eb = _load("export_boards")
_d8 = tempfile.mkdtemp(prefix="pt_ops_brd_")
_f8 = os.path.join(_d8, "boards_latest.csv")
_w(_f8, "board_name,board_type,member_code\n人工智能,concept,600001.XSHG\n")
# 周一(2026-10-26) -> 到期刷新；文件缺失也到期
ok("T8 周一固定到期", eb.boards_refresh_due(datetime.date(2026, 10, 26), _f8)[0] is True)
ok("T8 非周一跳过", eb.boards_refresh_due(datetime.date(2026, 10, 27), _f8)[0] is False)
ok("T8 文件缺失到期", eb.boards_refresh_due(datetime.date(2026, 10, 27), os.path.join(_d8, "none.csv"))[0] is True)
# 距上次 >=14 天兜底（防周一休市/失更）
_old = os.path.join(_d8, "old_boards.csv")
_w(_old, "board_name,board_type,member_code\n人工智能,concept,600001.XSHG\n")
_future = datetime.date(2026, 11, 11)   # 与 old_boards mtime(今天) 相差 >=14 天
ok("T8 >=14天兜底到期", eb.boards_refresh_due(_future, _old)[0] is True)
# run()：内容未变 UNCHANGED（不覆盖 mtime）；内容变化 WROTE
_m8 = os.path.join(_d8, "ths_board_mapping.json")
json.dump([{"board_name": "人工智能", "board_type": "concept", "code": "600001.SH", "board_rank": 1}], open(_m8, "w", encoding="utf-8"))
_d8b = tempfile.mkdtemp(prefix="pt_ops_brd2_")
_r1 = eb.run(mapping_path=_m8, out_dir=_d8b)
ok("T8 run WROTE", _r1["status"] == "WROTE" and _r1["boards"] == 1)
_r2 = eb.run(mapping_path=_m8, out_dir=_d8b)
ok("T8 run UNCHANGED 不覆盖", _r2["status"] == "UNCHANGED" and _r2["boards"] == 1)
json.dump([{"board_name": "人工智能", "board_type": "concept", "code": "600001.SH", "board_rank": 1},
           {"board_name": "AI算力", "board_type": "concept", "code": "600002.SH", "board_rank": 1}], open(_m8, "w", encoding="utf-8"))
_r3 = eb.run(mapping_path=_m8, out_dir=_d8b)
ok("T8 run 内容变化 WROTE", _r3["status"] == "WROTE" and _r3["boards"] == 2)

print("TOTAL pass=%d fail=%d" % (_p, _f))
raise SystemExit(1 if _f else 0)
