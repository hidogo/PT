# -*- coding: utf-8 -*-
"""AXquant 数据提供方对接契约（单一事实源）。

复盘链（PT run_one_click_after_close / closeout_review / export_lianban）消费 AXquant 复盘输出。
本模块集中定义：
- AXquant 项目根发现（env AXQUANT_PROJECT_DIR 优先，否则同级 D:/PROJ/AXquant）
- 各输入子目录布局：data/review、data/buys、data/special_snapshots、docs/review、
  data/position_expectation_<date>.jsonl
- 路径解析 probe / missing
- 一致性校验：预期 CSV vs 源 jsonl，zt 名单 vs limit_up_boards

目的：让一键收盘在"前置就绪校验 + 产出一致性核对"两处显性化，避免静默读到陈旧/缺失输入
（一致性：提供方目录布局、路径解析、行列契约单一来源，PT 不再散落硬编码）。
"""
from __future__ import annotations

import csv
import datetime as _dt
import io
import json
import os
import time


_HERE = os.path.dirname(os.path.abspath(__file__))          # .../research/expectation/bridge
_PROJ = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))   # D:/PROJ/PT
_DATA = os.path.join(_PROJ, "data")


def axquant_root() -> str:
    env = os.environ.get("AXQUANT_PROJECT_DIR", "").strip()
    if env and os.path.isdir(env):
        return os.path.abspath(env)
    sibling = os.path.abspath(os.path.join(_PROJ, "..", "AXquant"))
    return sibling if os.path.isdir(sibling) else env


def _ax(*parts) -> str:
    return os.path.join(axquant_root(), *parts)


# ---- 子目录布局（AXquant 对外数据契约） ----
SUB = {
    "review": ("data", "review"),
    "buys": ("data", "buys"),
    "snapshots": ("data", "special_snapshots"),
    "lub": ("docs", "review"),
}


def paths(review_date: str, next_date: str) -> dict:
    """按复盘日(review_date)与预期日(next_date)解析全部对接触点绝对路径。"""
    r = review_date or _dt.date.today().isoformat()
    n = next_date or ""
    return {
        "position_review":       _ax(*(SUB["review"] + ("position_review_%s.jsonl" % r,))),
        "open_reason":           _ax(*(SUB["buys"] + ("open_reason_%s.jsonl" % r,))),
        "special_snapshot":      _ax(*(SUB["snapshots"] + ("%s.json" % r,))),
        "limit_up_boards":       _ax(*(SUB["lub"] + ("limit_up_boards_%s.json" % r,))),
        "expectation_source":    _ax("data", "position_expectation_%s.jsonl" % (n or r)),
        "pt_review":             os.path.join(_DATA, "review", "position_review_%s.jsonl" % r),
        "bridge_dir":            os.environ.get("PTRADE_BRIDGE_OUT_DIR", "").strip() or os.path.join(_DATA, "ptrade_bridge"),
    }


def probe(review_date: str, next_date: str = "") -> list:
    """逐条探活，返回 [{key, path, exists, size, mtime, age_hours}]。"""
    out = []
    for key, p in paths(review_date, next_date).items():
        if key == "bridge_dir":
            continue
        ex = os.path.isfile(p)
        item = {"key": key, "path": p, "exists": ex, "size": 0, "mtime": "", "age_hours": None,
                "marker": False, "marker_reason": ""}
        if ex:
            item["size"] = os.path.getsize(p)
            mt = os.path.getmtime(p)
            item["mtime"] = time.strftime("%Y-%m-%d %H:%M", time.localtime(mt))
            item["age_hours"] = round((time.time() - mt) / 3600.0, 2)
            if key in ("position_review", "expectation_source"):
                _m, _r = _marker_detect(p)
                item["marker"] = _m
                item["marker_reason"] = _r
        out.append(item)
    return out


def _marker_detect(path):
    # 识别空 marker 复盘/预期文件（record_type=*_marker / position_status=空仓|无法判定 / 无数据行）。
    # 文件存在但内容为空壳 = 本地持仓桥接或复盘任务未真正产出（10-19/10-20 实测 position_ok=false 场景），
    # 预期链路会空转——这是断链的显性信号。
    # 仅当 ALL 行都是 marker 才判空 marker；首行 marker + 后随真实复盘行 = 正常（write_position_review 补记后追加真实记录）。
    try:
        n_data = 0
        marker_rows = 0
        first_reason = ""
        with io.open(path, "r", encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if not ln:
                    continue
                n_data += 1
                try:
                    rec = json.loads(ln)
                except Exception:
                    continue
                rt = str(rec.get("record_type") or "")
                ps = str(rec.get("position_status") or "")
                if "marker" in rt or ps in ("空仓", "无法判定"):
                    marker_rows += 1
                    if not first_reason:
                        first_reason = (("record_type=" + rt) if rt else ("position_status=" + ps))
        if n_data == 0:
            return True, "no_data_rows"
        if marker_rows == n_data:
            return True, first_reason
        return False, ""
    except Exception:
        return False, ""


def missing(review_date: str, next_date: str = "") -> list:
    """返回缺失的关键对接触点 key 列表（仅输入类）。"""
    have = {i["key"] for i in probe(review_date, next_date) if i["exists"]}
    need = ["position_review", "limit_up_boards", "expectation_source"]
    return [k for k in need if k not in have]


def limit_up_rows(review_date: str) -> list:
    """读 AXquant 涨停池快照 pool.item；缺文件返回 []。"""
    p = paths(review_date, "")["limit_up_boards"]
    try:
        with io.open(p, "r", encoding="utf-8") as f:
            payload = json.load(f)
        pool = (payload or {}).get("pool") or {}
        return [it for it in (pool.get("item") or []) if isinstance(it, dict)]
    except Exception:
        return []


def check_zt_consistency(zt_csv_path: str, review_date: str) -> dict:
    """核对 zt_lianban CSV 行数与 limit_up_boards pool 条数、date 标签一致。"""
    res = {"ok": False, "zt_rows": 0, "board_rows": 0, "zt_date": "", "note": ""}
    rows = list(csv.DictReader(io.open(zt_csv_path, "r", encoding="utf-8"))) if os.path.isfile(zt_csv_path) else []
    res["zt_rows"] = len(rows)
    res["zt_date"] = rows[0].get("date", "") if rows else ""
    brs = limit_up_rows(review_date)
    res["board_rows"] = len(brs)
    res["ok"] = (len(rows) == len(brs)) and bool(rows) and res["zt_date"] == review_date
    if not res["ok"]:
        res["note"] = "zt_rows=%d board_rows=%d zt_date=%s" % (res["zt_rows"], res["board_rows"], res["zt_date"])
    return res




def _num(x):
    return str(x or "").split(".")[0].strip()

def _expected_pt(x):
    """按数字代码前缀推断正确市场后缀（与云端 _norm_sec 同口径）。"""
    n = _num(x)
    if n.startswith(("300", "301", "002", "003", "000", "001")):
        return n + ".XSHE"
    return n + ".XSHG"

def _fam(x):
    s = str(x or "").split(".")[-1].lower()
    if s in ("sz", "xshe"):
        return "SZ"
    if s in ("bj", "xbj"):
        return "BJ"
    return "SH"

def _exp_fam(x):
    n = _num(x)
    return "SZ" if n.startswith(("300", "301", "002", "003", "000", "001")) else "SH"

def _pt_note(_cc, _sc, csv_codes, src_codes):
    # 数字一致但市场后缀族错误（如深市写 .SH / 600xxx 写 .SZ）单独上报；AX/PT 后缀惯例差异不算异常
    anom = []
    for c in list(csv_codes) + list(src_codes):
        n = _num(c)
        if n and _fam(c) != _exp_fam(c):
            anom.append("%s->%s(exp %s)" % (n, str(c).split(".")[-1], _exp_fam(c)))
    return (" suffix_anomalies=%s" % sorted(set(anom))) if anom else ""

def _pt(x):
    """AX(.SH/.SZ/.BJ) 与 PT(.XSHG/.XSHE/.XBJ) 代码归一为 PT 风格，跨源比对用。"""
    x = str(x or "").strip()
    if not x:
        return ""
    head = x.split(".")[0]
    low = x.lower()
    if ".sz" in low:
        return head + ".XSHE"
    if ".bj" in low:
        return head + ".XBJ"
    return head + ".XSHG"


def check_expectation_consistency(csv_path: str, source_jsonl: str) -> dict:
    """核对预期 CSV 的 code 集合与源 position_expectation jsonl 一致。"""
    res = {"ok": False, "csv_codes": 0, "src_codes": 0, "note": ""}
    csv_codes = []
    if os.path.isfile(csv_path):
        for row in csv.DictReader(io.open(csv_path, "r", encoding="utf-8")):
            c = (row.get("code") or "").strip()
            if c:
                csv_codes.append(c)
    src_codes = []
    if os.path.isfile(source_jsonl):
        with io.open(source_jsonl, "r", encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    rec = json.loads(ln)
                except Exception:
                    continue
                c = str(rec.get("code") or rec.get("thscode") or rec.get("symbol") or "").strip()
                if c:
                    src_codes.append(c)
    _cc = {_pt(c) for c in csv_codes}
    _sc = {_pt(c) for c in src_codes}
    res["csv_codes"] = len(_cc)
    res["src_codes"] = len(_sc)
    res["ok"] = ({_num(c) for c in _cc} == {_num(c) for c in _sc}) and bool(_cc)
    if not res["ok"]:
        res["note"] = "only-in-csv=%s only-in-src=%s" % (
            sorted({_num(c) for c in _cc} - {_num(c) for c in _sc}),
            sorted({_num(c) for c in _sc} - {_num(c) for c in _cc}))
    else:
        res["note"] = _pt_note(_cc, _sc, csv_codes, src_codes)
    return res


def probe_report(review_date: str, next_date: str = "") -> None:
    print("[provider] AXquant root = %s" % axquant_root())
    warns = []
    for it in probe(review_date, next_date):
        if it["exists"] and it["marker"]:
            st = "MARK"
            warns.append("%s=%s" % (it["key"], it["marker_reason"]))
        else:
            st = "OK " if it["exists"] else "MISS"
        print("  [%s] %-22s %s size=%s mtime=%s age_h=%s%s" % (
            st, it["key"], it["path"], it["size"], it["mtime"], it["age_hours"],
            ("  <- 空 marker(%s)" % it["marker_reason"]) if it.get("marker") else ""))
    if warns:
        print("  [WARN] 检测到空 marker（文件存在但无真实复盘/预期内容，预期链路可能空转）: %s" % "; ".join(warns))


def marker_warns(review_date: str, next_date: str = "") -> list:
    """返回空 marker 断链告警列表（供一键脚本在步骤0 显性提示）。"""
    return ["%s(%s)" % (it["key"], it["marker_reason"])
            for it in probe(review_date, next_date) if it["exists"] and it["marker"]]