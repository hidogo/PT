#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PT 独立生成 Ptrade 桥接预期 CSV（自包含，零 axquant 依赖）。

自动上传形态：Ptrade「定时上传＝绑定本地文件夹路径，逐文件读取该文件夹内文件上送」，
并非单一固定文件名。故本工具把桥接目录当“待上传文件夹”管理：

  <PTRADE_BRIDGE_DIR>/
      expectation_<YYYY-MM-DD>.csv     待上传根：只放当天日期命名的 CSV
      archive/                         不上传归档：识别元数据 + 今日稳定指针 + 历史文件
          expectation_<日>.csv.meta.json
          ptrade_today.csv

子命令:
  from-jsonl --date YYYY-MM-DD [--source PATH] [--out-dir DIR]
      预期 JSONL -> 待上传 CSV（根） + archive（meta/今日指针）；默认保留最近1个日期、清理更早。
  validate  --date YYYY-MM-DD [--out-dir DIR]
      按文件夹上传前校验根目录当天 CSV 的完整性与新鲜度（自动上传文件识别）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import bridge  # noqa: E402


CSV_HEADER = [
    "code", "side", "entry_type", "expected_status", "yesterday_open_pct",
    "expected_auction_change_pct", "seal_amount_t0", "board_name", "reason",
]


def _sha1(path: str) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _resolve_trade_date(td: str | None) -> str:
    return td or _today_str()


def _prune_older(out_dir: str, keep_days: int) -> None:
    """待上传根只保留最近 keep_days 个日期 CSV，更早移除（防历史被自动上传带上云）。

    只匹配 expectation_YYYY-MM-DD.csv 命名、且路径在 out_dir 内，杜绝误删。
    """
    pat = re.compile(r"^expectation_(\d{4}-\d{2}-\d{2})\.csv$")
    dated = []
    for name in os.listdir(out_dir):
        m = pat.match(name)
        if not m:
            continue
        full = os.path.join(out_dir, name)
        if not os.path.isfile(full):
            continue
        dated.append((m.group(1), full))
    dated.sort()
    for _, full in dated[:-keep_days]:
        try:
            os.remove(full)
            print("  prune:", full)
        except OSError:
            pass


def cmd_from_jsonl(args: argparse.Namespace) -> int:
    td = _resolve_trade_date(args.date)
    src = args.source or ""
    if not src:
        local = bridge.default_expectation_path(td)
        if os.path.isfile(local):
            src = local
        else:
            ax = os.path.abspath(os.path.join(
                bridge.expectation_store._expectation_data_dir(),
                "..", "..", "AXquant", "data", "position_expectation_%s.jsonl" % td))
            if os.path.isfile(ax):
                src = ax
    if not src or not os.path.isfile(src):
        print("[from-jsonl] 找不到预期 JSONL（本地与 AXquant 兜底均无）", file=sys.stderr)
        return 2

    out_dir = args.out_dir or bridge.PTRADE_BRIDGE_DIR
    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, "expectation_%s.csv" % td)
    archive_dir = os.path.join(out_dir, "archive")
    os.makedirs(archive_dir, exist_ok=True)
    meta_path = os.path.join(archive_dir, "expectation_%s.csv.meta.json" % td)
    today_path = os.path.join(archive_dir, "ptrade_today.csv")

    rows = bridge.expectation_store.export_expectation_csv(td, out_path=csv_path, src_path=src)
    if rows <= 0:
        print("[from-jsonl] 未导出任何行（recs 为空）", file=sys.stderr)
        return 3

    meta = {
        "trade_date": td,
        "source": src,
        "row_count": rows,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "sha1": _sha1(csv_path),
        "header": CSV_HEADER,
        "note": "供 Ptrade 自动上传识别：日期匹配 + 行数>0 + 哈希一致才视为可用。",
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    tmp = today_path + ".tmp"
    with open(tmp, "wb") as f:
        with open(csv_path, "rb") as s:
            f.write(s.read())
    bridge.expectation_store.replace_file_retry(tmp, today_path)

    _prune_older(out_dir, keep_days=max(1, args.keep_days))
    print("[from-jsonl] 完成 rows=%d" % rows)
    print("  upload root :", csv_path)
    print("  archive meta:", meta_path)
    print("  archive today:", today_path)
    return 0


def _read_jsonl(path):
    out = []
    if not path or not os.path.isfile(path):
        return out
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def _snapshot_map_from_file(path):
    m = {}
    if not path or not os.path.isfile(path):
        return m
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return m
    for v in data.values():
        if isinstance(v, list):
            for it in v:
                if isinstance(it, dict) and it.get("code"):
                    m.setdefault(str(it["code"]), it)
    return m


def _next_date(dstr):
    # 下一交易日（跳过周末；精确节假日由权威缓存决定，见 bridge.calendar）
    import datetime as _dt
    d = _dt.date.fromisoformat(dstr)
    return bridge.calendar.next_trading_day(d).isoformat()



def _init_expectation_from_review(rev, trade_date, review_date):
    t1 = rev.get("t1_expectation") or {}
    primary = str(t1.get("primary") or "").lower()
    status = ("pending_" + primary) if primary in ("exceed", "meet", "miss") else "awaiting_auction"
    return {
        "trade_date": trade_date,
        "code": rev.get("code"),
        "review_date": review_date,
        "role": rev.get("role") or "",
        "role_detail": rev.get("role_detail") or "",
        "junk_follower": bool(rev.get("junk_follower")),
        "sell_policy_hint": rev.get("sell_policy_hint") or "",
        "entry_type": rev.get("entry_type") or "normal",
        "status": status,
        "auction_status": "",
        "intraday_status": "",
        "auction_change_pct": rev.get("auction_change_pct"),
        "opened_above_yesterday": rev.get("opened_above_yesterday"),
        "yesterday_open_pct": rev.get("yesterday_open_pct"),
        "seal_amount_t0": rev.get("seal_amount_t0") or 0,
        "board_name": rev.get("board_name") or "",
        "reasons": ["rebuilt_from_review"],
        "updated_at": datetime.now().isoformat(timespec="milliseconds"),
        "extra": {"rebuilt_by": "pt_bridge_cli", "t1_expectation": t1},
    }


def _default_positions(ex, td):
    # 默认读本地收盘同步的持仓 JSON（见 sync_positions.py）
    cand = os.path.join(ex._expectation_data_dir(), 'positions', 'positions_%s.json' % td)
    if not os.path.isfile(cand):
        return []
    try:
        with open(cand, 'r', encoding='utf-8') as f:
            data = json.load(f) or {}
        plist = data.get('positions') or []
        return [p for p in plist if p.get('code')]
    except Exception:
        return []
    

def cmd_review(args):
    td = _resolve_trade_date(args.date)
    next_td = args.next_date or _next_date(td)
    ex = bridge.expectation_store

    ore_path = args.open_reason or ""
    if not ore_path:
        local = ex.default_open_reason_path(td)
        if os.path.isfile(local):
            ore_path = local
        else:
            _d = ex._expectation_data_dir()
            ax = os.path.abspath(os.path.join(_d, "..", "..", "AXquant", "data",
                                              "buys", "open_reason_%s.jsonl" % td))
            if os.path.isfile(ax):
                ore_path = ax
    if not ore_path or not os.path.isfile(ore_path):
        print("[review] 找不到 open_reason JSONL", file=sys.stderr)
        return 2
    open_reasons = [r for r in _read_jsonl(ore_path)
                    if str(r.get("status") or "").lower() in ("filled", "partial")]

    snap_path = args.snapshots or ""
    if not snap_path:
        _d = ex._expectation_data_dir()
        local = os.path.join(_d, "special_snapshots", "%s.json" % td)
        if os.path.isfile(local):
            snap_path = local
        else:
            _d = ex._expectation_data_dir()
            ax = os.path.abspath(os.path.join(_d, "..", "..", "AXquant", "data",
                                              "special_snapshots", "%s.json" % td))
            if os.path.isfile(ax):
                snap_path = ax
    snapshot_map = _snapshot_map_from_file(snap_path)

    positions = _read_jsonl(args.positions) if args.positions else _default_positions(ex, td)
    insights = {}
    if args.insights and os.path.isfile(args.insights):
        with open(args.insights, "r", encoding="utf-8") as f:
            insights = json.load(f) or {}

    confirmed = []
    seen = set()
    for r in open_reasons:
        code = str(r.get("code") or "")
        if not code or code in seen:
            continue
        seen.add(code)
        confirmed.append(r)
    for p in positions:
        code = str(p.get("code") or "")
        if not code or code in seen:
            continue
        seen.add(code)
        confirmed.append({
            "trade_date": td,
            "code": code,
            "name": str(p.get("name") or ""),
            "scenario": "position_fallback",
            "price": float(p.get("cost") or p.get("price") or 0),
            "volume": int(p.get("volume") or 0),
            "status": "filled",
            "source_agent": "position_fallback",
            "tags": [],
        })

    records = []
    if confirmed:
        try:
            records = bridge.make_review_records(td, confirmed, snapshot_map,
                                                 insights, set(), {}, {})
        except Exception as exc:
            print("[review] make_review_records 出错: %s" % exc, file=sys.stderr)
            return 4

    review_path = args.review_out or ex.default_review_path(td)
    if records:
        ex.write_position_reviews(td, records, path=review_path)

    expected = [_init_expectation_from_review(r.to_dict(), next_td, td) for r in records]
    exp_path = args.expectation_out or ex.default_expectation_path(next_td)
    if expected:
        ex.write_expectation_records(next_td, expected, path=exp_path)

    out_dir = args.out_dir or bridge.PTRADE_BRIDGE_DIR
    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, "expectation_%s.csv" % next_td)
    rows = ex.export_expectation_csv(next_td, out_path=csv_path, src_path=exp_path)

    print("[review] 复盘 %s -> 预期 %s: records=%d 预期行=%s" % (td, next_td, len(records), rows))
    print("  review  :", review_path)
    print("  expected:", exp_path)
    print("  csv     :", csv_path)
    return 0



def cmd_calendar(args):
    import datetime as _dt
    cal = bridge.calendar
    base = _dt.date.today() if not args.date else _dt.date.fromisoformat(args.date)
    print('date=%s trading=%s prev=%s next=%s' % (
        base.isoformat(), cal.is_trading_day(base),
        cal.previous_trading_day(base).isoformat(), cal.next_trading_day(base).isoformat()))
    print('cache:', cal.cache_path(), 'exists:', os.path.isfile(cal.cache_path()))
def cmd_validate(args: argparse.Namespace) -> int:
    td = _resolve_trade_date(args.date)
    out_dir = args.out_dir or bridge.PTRADE_BRIDGE_DIR
    csv_path = os.path.join(out_dir, "expectation_%s.csv" % td)
    meta_path = os.path.join(out_dir, "archive", "expectation_%s.csv.meta.json" % td)

    problems = []
    if not os.path.isfile(csv_path):
        problems.append("缺少当天 CSV")
    else:
        st = os.stat(csv_path)
        age_min = (datetime.now().timestamp() - st.st_mtime) / 60.0
        with open(csv_path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
        header = lines[0][1:] if lines and lines[0].startswith("\ufeff") else (lines[0] if lines else "")
        if not lines:
            problems.append("CSV 为空")
        elif header.split(",") != CSV_HEADER:
            problems.append("表头不匹配")
        if len(lines) <= 1:
            problems.append("无数据行")
        if age_min > 720:
            problems.append("文件过旧(%.0f分钟)" % age_min)
        if os.path.isfile(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            if str(meta.get("trade_date")) != td:
                problems.append("meta 日期不匹配")
            if meta.get("row_count") != max(0, len(lines) - 1):
                problems.append("行数与 meta 不符")
            if meta.get("sha1") != _sha1(csv_path):
                problems.append("哈希不一致(可能被改动)")
    if problems:
        print("[validate] 未通过:", "; ".join(problems))
        return 1
    print("[validate] 通过 row_count=%d" % max(0, len(lines) - 1))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="build_expectation_bridge",
                                description="PT 独立生成 Ptrade 桥接预期 CSV")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("from-jsonl", help="预期 JSONL -> 待上传 CSV(+archive meta/今日指针)")
    a.add_argument("--date", default="", help="YYYY-MM-DD，默认今日")
    a.add_argument("--source", default="", help="显式指定 position_expectation JSONL")
    a.add_argument("--out-dir", default="", help="输出目录，默认 PTRADE_BRIDGE_DIR")
    a.add_argument("--keep-days", type=int, default=1, help="待上传根保留最近几个日期 CSV，默认1")
    a.set_defaults(fn=cmd_from_jsonl)

    rv = sub.add_parser("review", help="本地完整复盘重建：涨停池+持仓+复盘洞察 -> 复盘 -> 预期 CSV")
    rv.add_argument("--date", default="", help="复盘日 YYYY-MM-DD，默认今日")
    rv.add_argument("--next-date", default="", help="预期交易日 T+1，默认复盘日次日")
    rv.add_argument("--open-reason", default="", help="open_reason JSONL")
    rv.add_argument("--snapshots", default="", help="涨停池快照 JSON（单个文件）")
    rv.add_argument("--positions", default="", help="持仓 JSON（可选）")
    rv.add_argument("--insights", default="", help="复盘洞察 JSON（可选）")
    rv.add_argument("--review-out", default="", help="复盘 JSONL 输出")
    rv.add_argument("--expectation-out", default="", help="预期 JSONL 输出")
    rv.add_argument("--out-dir", default="", help="CSV 输出目录")
    rv.set_defaults(fn=cmd_review)
    
    ck = sub.add_parser("calendar", help="查询交易日历(是否交易日/上一交易日/下一交易日)")
    ck.add_argument("--date", default="", help="YYYY-MM-DD，默认今日")
    ck.set_defaults(fn=cmd_calendar)
    
    b = sub.add_parser("validate", help="按文件夹上传前校验当天 CSV")
    b.add_argument("--date", default="", help="YYYY-MM-DD，默认今日")
    b.add_argument("--out-dir", default="", help="输出目录")
    b.set_defaults(fn=cmd_validate)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())