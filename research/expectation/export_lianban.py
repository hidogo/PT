#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""导涨停池/连板名单（AXquant limit_up_boards_*.json）为云端可读 CSV。

数据契约（列）：
  date,code,name,board_cnt,limit_up_time,seal_money,chg_pct,is_st,reason

文件落到与预期 CSV 同一「待上传文件夹」PTRADE_BRIDGE_DIR（客户端定时上传会带上）：
  zt_lianban_<date>.csv   该日 T-1 涨停池（date=涨停池数据日, 收盘后为 T-1）
  zt_lianban_latest.csv   稳定指针 = 最近一版内容（云端直接读最新 T-1, 避免云端算交易日历）
仅保留最近 keep_days(默认3) 个日期文件。

用法：
  python export_lianban.py [--date 2026-10-16] [--lub <axquant json 目录>] [--out-dir <上传文件夹>]
"""
from __future__ import annotations
import argparse, datetime, glob, json, os, re
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
import bridge  # noqa: E402  # 复用 PTRADE_BRIDGE_DIR / 数据目录常量
from bridge.expectation_store import _expectation_data_dir  # noqa: E402
from bridge.publish import derive_closing_board_status  # noqa: E402  # v0.37 AXquant 同源收盘地位重算（唯一身位/跟风数）


def _code_ptrade(thscode: str) -> str:
    # AXquant .SH/.SZ/.BJ -> Ptrade .XSHG/.XSHE/.XBJ（与 expectation 桥接同映射）
    s = str(thscode or "").strip().split(".")[0]
    low = str(thscode or "").lower()
    if ".sz" in low:
        return s + ".XSHE"
    if ".bj" in low:
        return s + ".XBJ"
    return s + ".XSHG"


def _default_axquant_lub_dir() -> str:
    # PT research/expectation -> 项目根(D:/PROJ/PT) -> 上一级(D:/PROJ) 下的 AXquant/docs/review
    return os.path.abspath(os.path.join(_HERE, "..", "..", "..", "AXquant", "docs", "review"))


def default_lub_path(date: str, lub_dir: str | None = None) -> str:
    return os.path.join(lub_dir or _default_axquant_lub_dir(), "limit_up_boards_%s.json" % date)


def _extract_pool_rows(payload: dict) -> list[dict]:
    pool = (payload or {}).get("pool") or {}
    items = pool.get("item") or []
    rows = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        rows.append({
            "code": _code_ptrade(it.get("thscode") or ""),
            "name": str(it.get("name") or ""),
            "board_cnt": int(it.get("continue_day_cnt") or 0),
            "limit_up_time": str(it.get("limit_up_time") or ""),
            "seal_money": float(it.get("seal_money") or 0.0),
            "chg_pct": float(it.get("price_change_ratio_pct") or 0.0),
            "is_st": 1 if it.get("is_st") else 0,
            "reason": str(it.get("limit_up_reason") or ""),
        })
    return rows


def _pool_missing(payload: dict, rows) -> int:
    # 分页完整性护栏：涨停池 item 数 < pagination.total 视为被截断(可能遗漏)，返回缺多少
    pg = ((payload or {}).get("pool") or {}).get("pagination") or {}
    total = pg.get("total")
    if total and int(total) != len(rows or []):
        return int(total) - len(rows or [])
    return 0


def build_csv(date: str, rows: list[dict], unq: dict | None = None) -> str:
    # v0.37 追加权威唯一身位列（AXquant 同源收盘地位重算 derive_closing_board_status）：
    #   unique_high / follower_count，云端读列优先、缺列回退首 token 兜底。
    unq = unq or {}
    head = "date,code,name,board_cnt,limit_up_time,seal_money,chg_pct,is_st,reason,unique_high,follower_count"
    lines = [head]
    for r in rows:
        reason = r["reason"].replace(",", " ").replace("\n", " ").strip()
        u = unq.get(r["code"]) or {}
        uh = 1 if u.get("unique_high_board") else 0
        fc = int(u.get("follower_count") or 0)
        lines.append("%s,%s,%s,%d,%s,%.2f,%.4f,%d,%s,%d,%d" % (
            date, r["code"], r["name"].replace(",", " "), r["board_cnt"],
            r["limit_up_time"], r["seal_money"], r["chg_pct"], r["is_st"], reason, uh, fc))
    return "\n".join(lines) + "\n"


def _clean_old(out_dir: str, keep_days: int) -> None:
    pat = re.compile(r"^zt_lianban_(\d{4}-\d{2}-\d{2})\.csv$")
    dated = []
    for fp in glob.glob(os.path.join(out_dir, "zt_lianban_*.csv")):
        base = os.path.basename(fp)
        m = pat.match(base)
        if m:
            dated.append((m.group(1), fp))
    dated.sort()
    for _day, fp in dated[:-max(1, int(keep_days))]:
        try:
            os.remove(fp)
        except OSError:
            pass


def run(date: str | None = None, lub_dir: str | None = None, out_dir: str | None = None,
        keep_days: int = 3, alias: str = "") -> str:
    """返回导出的待上传 CSV 路径（未找到涨停池 json 时返回空串）。"""
    date = date or datetime.date.today().isoformat()
    out_dir = out_dir or bridge.PTRADE_BRIDGE_DIR
    lub = default_lub_path(date, lub_dir)
    if not os.path.exists(lub):
        print("[zt-lianban] 未找到涨停池 %s —— 跳过(等 AXquant 产出)" % lub)
        return ""
    with open(lub, "r", encoding="utf-8") as f:
        payload = json.load(f)
    rows = _extract_pool_rows(payload)
    _miss = _pool_missing(payload, rows)
    if _miss:
        raise ValueError("涨停池分页不完整 item=%d total=%d(缺%d)，停止写名单"
                         % (len(rows), int(((payload or {}).get("pool") or {}).get("pagination", {}).get("total") or 0), _miss))
    if not rows:
        print("[zt-lianban] %s 涨停池为空, 不导出" % date)
        return ""
    csv_path = os.path.join(out_dir, "zt_lianban_%s.csv" % date)
    latest = os.path.join(out_dir, "zt_lianban_latest.csv")
    unq = {}
    try:
        _st = derive_closing_board_status(date, boards_dir=Path(lub_dir or _default_axquant_lub_dir()))
        unq = {_code_ptrade(c): s for c, s in (_st or {}).items()}
    except Exception as e:
        print("[zt-lianban] 唯一身位重算跳过(回退云端首token): %r" % e)
    content_b = build_csv(date, rows, unq).encode("utf-8")
    extra = [os.path.join(out_dir, alias)] if alias else []
    for fp in tuple([csv_path, latest]) + tuple(extra):
        try:
            with open(fp, "wb") as f:
                f.write(content_b)
        except OSError as e:
            print("[zt-lianban] 写 %s 失败 %r" % (fp, e))
    _clean_old(out_dir, keep_days)
    print("[zt-lianban] %s -> %d 只 连板最高=%d 已导出 %s (latest=%s)"
          % (date, len(rows), max((r["board_cnt"] for r in rows), default=0), csv_path, latest))
    return csv_path


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="export_lianban", description="导出 AXquant 涨停池/连板名单为国家市 CSV")
    p.add_argument("--date", default="", help="涨停池数据日(收盘日 T-1) YYYY-MM-DD")
    p.add_argument("--lub", default="", help="AXquant 涨停池 json 目录(默认自动定位 D:/PROJ/AXquant/docs/review)")
    p.add_argument("--out-dir", default="", help="待上传文件夹(默认 PTRADE_BRIDGE_DIR)")
    p.add_argument("--keep-days", type=int, default=3)
    a = p.parse_args(argv)
    return 0 if run(a.date or None, a.lub or None, a.out_dir or None, a.keep_days) else 1


if __name__ == "__main__":
    raise SystemExit(main())
