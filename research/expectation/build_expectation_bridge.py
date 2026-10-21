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
import bridge.axquant_contract as axc  # noqa: E402


CSV_HEADER = [
    "code", "name", "side", "entry_type", "expected_status", "yesterday_open_pct",
    "expected_auction_change_pct", "seal_amount_t0", "board_name", "reason",
    "sell_policy_hint", "role_detail",
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
        if _usable_expectation_source(local):
            src = local
        else:
            share = axc.expectation_source_path(td)
            if _usable_expectation_source(share):
                src = share
            else:
                ax = os.path.abspath(os.path.join(
                    bridge.expectation_store._expectation_data_dir(),
                    "..", "..", "AXquant", "data", "position_expectation_%s.jsonl" % td))
                if _usable_expectation_source(ax):
                    src = ax
    if not src or not os.path.isfile(src):
        print("[from-jsonl] 找不到预期 JSONL（本地 / ShareData / AXquant 兜底均无）", file=sys.stderr)
        return 2

    out_dir = args.out_dir or bridge.PTRADE_BRIDGE_DIR
    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, "expectation_%s.csv" % td)
    archive_dir = os.path.join(out_dir, "archive")
    os.makedirs(archive_dir, exist_ok=True)
    meta_path = os.path.join(archive_dir, "expectation_%s.csv.meta.json" % td)
    today_path = os.path.join(archive_dir, "ptrade_today.csv")

    # 回填空白昨日开盘涨幅（review 值 verbatim；缺失再日线 open/close 兜底）
    import datetime as _dt
    review_day = bridge.calendar.previous_trading_day(_dt.date.fromisoformat(td)).isoformat()
    _recs = _read_jsonl(src)
    _n = _correct_yopen(_recs, review_day)
    if _n:
        _src_raw = src
        _norm = os.path.join(out_dir, "archive", "expectation_%s.normalized.jsonl" % td)
        with open(_norm, "w", encoding="utf-8") as _f:
            for _r in _recs:
                _f.write(json.dumps(_r, ensure_ascii=False, default=str) + "\n")
        src = _norm
        # 源为本地预期 jsonl 时同步写回，保证持久化与导出一致（AXquant 只读源不覆盖）
        try:
            _local = bridge.expectation_store.default_expectation_path(td)
            if _src_raw and os.path.abspath(_src_raw) == os.path.abspath(_local):
                with open(_src_raw, "w", encoding="utf-8") as _f2:
                    for _r in _recs:
                        _f2.write(json.dumps(_r, ensure_ascii=False, default=str) + "\n")
        except Exception:
            pass
        print("[from-jsonl] 修正昨日开盘涨幅 %d 行(open(S)/close(S-1))" % _n)
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


def _usable_expectation_source(path):
    """候选源需含至少一条带 code 的预期记录（跳过空文件/仅 marker 终态，防空文件抢占）。"""
    if not path or not os.path.isfile(path):
        return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if isinstance(rec, dict) and rec.get("code"):
                    return True
    except Exception:
        return False
    return False


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



def _ptrade_to_ax(code):
    """Ptrade .XSHG/.XSHE/.XBJ -> AXquant .SH/.SZ/.BJ（回填昨日开盘涨幅用）。"""
    c = str(code or "").strip()
    if not c:
        return ""
    parts = c.split(".")
    head = parts[0]
    suf = parts[1].upper() if len(parts) > 1 else ""
    if suf in ("XSHG", "SH", "SHANGHAI"):
        return head + ".SH"
    if suf in ("XSHE", "SZ", "SHENZHEN"):
        return head + ".SZ"
    if suf in ("XBJ", "BJ", "BEIJING"):
        return head + ".BJ"
    return head + (".SH" if head[:1] in ("6", "5", "9") else ".SZ")


def _review_auction_map(review_date):
    """读 review(开盘复盘) jsonl 的 auction_change_pct（review 日自身开盘涨幅 open(S)/close(S-1)-1）。

    语义：T+1 的"昨日"= review 日 S，昨日开盘涨幅应取 S 自身开盘涨幅（=review auction_change_pct），
    而非 review 存的 yesterday_open_pct（那是 open(S-1)/close(S-2)，2 天滞后的值）。"""
    m = {}
    if not review_date:
        return m
    cands = []
    _ax = os.path.join(_HERE, "..", "..", "..", "AXquant", "data", "review",
                       "position_review_%s.jsonl" % review_date)
    _pt = os.path.join(_HERE, "..", "..", "data", "review",
                       "position_review_%s.jsonl" % review_date)
    for p_ in (_ax, _pt):
        if os.path.isfile(p_):
            cands.append(p_)
    for p_ in cands:
        for r in _read_jsonl(p_):
            v = r.get("auction_change_pct")
            if v is None or v == "":
                continue
            code = str(r.get("code") or "").strip()
            if code:
                m[code] = round(float(v), 2)
    return m
    m = {}
    if not review_date:
        return m
    cands = []
    _ax = os.path.join(_HERE, "..", "..", "..", "AXquant", "data", "review",
                       "position_review_%s.jsonl" % review_date)
    _pt = os.path.join(_HERE, "..", "..", "data", "review",
                       "position_review_%s.jsonl" % review_date)
    for p_ in (_ax, _pt):
        if os.path.isfile(p_):
            cands.append(p_)
    for p_ in cands:
        for r in _read_jsonl(p_):
            v = r.get("yesterday_open_pct")
            if v is None or v == "":
                continue
            code = str(r.get("code") or "").strip()
            if code:
                m[code] = round(float(v), 2)
    return m


def _daily_yopen_from_net(ax_code, review_date):
    """日线 open/close 兜底：open(review日)/close(review前一日)-1（review 日自身开盘涨幅）。

    用 akshare 拉近 10 日日K，磁盘缓存到 data/kline_cache；失败/回撤返回 None（不阻断）。
    """
    if not ax_code or not review_date or "." not in ax_code:
        return None
    sym = ax_code.split(".")[0]
    cache_dir = os.path.join(_HERE, "..", "..", "data", "kline_cache")
    try:
        os.makedirs(cache_dir, exist_ok=True)
    except Exception:
        cache_dir = None
    cpath = os.path.join(cache_dir, "%s_%s.json" % (sym, review_date)) if cache_dir else ""
    data = None
    if cpath and os.path.isfile(cpath):
        try:
            with open(cpath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = None
    if not data or not data.get("rows"):
        try:
            import akshare as ak
            import datetime as _dt
            start = (_dt.date.fromisoformat(review_date) - _dt.timedelta(days=10)).isoformat().replace("-", "")
            end = review_date.replace("-", "")
            df = ak.stock_zh_a_hist(symbol=sym, period="daily",
                                    start_date=start, end_date=end, adjust="")
            rows = []
            if df is not None:
                for _, r in df.iterrows():
                    rows.append({"date": str(r["日期"])[:10],
                                 "open": float(r["开盘"]), "close": float(r["收盘"])})
            data = {"code": ax_code, "rows": rows}
            if cpath:
                with open(cpath, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False)
        except Exception:
            data = None
    rows = (data or {}).get("rows") or []
    if not rows:
        return None
    rows = sorted(rows, key=lambda r: r["date"])
    idx = [i for i, r in enumerate(rows) if str(r["date"]) == review_date]
    if not idx:
        return None
    i = idx[0]
    if i < 1:
        return None
    o = rows[i]["open"]; pc = rows[i - 1]["close"]
    if not o or not pc or pc <= 0:
        return None
    return round((o / pc - 1.0) * 100.0, 2)


def _has_yopen(rec):
    v = rec.get("yesterday_open_pct")
    return v is not None and v != ""


def _correct_yopen(records, review_date, net_fetch=True):
    """统一修正昨日开盘涨幅=review 日自身开盘涨幅 open(S)/close(S-1)-1（T+1 的昨日=review 日 S）。

    原记录存 open(S-1)/close(S-2)（2 天滞后），与云端 _eval_auction 的 chg>yesterday 语义不符；
    本函数覆盖为 S 自身开盘涨幅（review auction_change_pct 优先，日线 open/close 兜底）。返回修改行数。
    """
    if not records:
        return 0
    rmap = _review_auction_map(review_date)
    n = 0
    for r in records:
        ax = _ptrade_to_ax(str(r.get("code") or ""))
        v = rmap.get(ax)
        if v is None and net_fetch:
            v = _daily_yopen_from_net(ax, review_date)
        if v is None:
            continue
        old = r.get("yesterday_open_pct")
        r["yesterday_open_pct"] = v
        try:
            if old is None or old == "" or abs(float(old) - float(v)) > 1e-9:
                n += 1
        except Exception:
            n += 1
    return n




def _init_expectation_from_review(rev, trade_date, review_date):
    t1 = rev.get("t1_expectation") or {}
    primary = str(t1.get("primary") or "").lower()
    status = ("pending_" + primary) if primary in ("exceed", "meet", "miss") else "awaiting_auction"
    return {
        "trade_date": trade_date,
        "code": rev.get("code"),
        "name": rev.get("name") or "",
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
        # v0.31b 降级：无成交日或供方缺失 open_reason 时不阻断收盘链路，仅用持仓/涨停池复盘
        print("[review] open_reason 缺失（无成交日或供方未产出）—— 降级：仅用持仓/涨停池复盘", file=sys.stderr)
        open_reasons = []
    else:
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
    _n = _correct_yopen(expected, td)
    if _n:
        print("[review] 修正昨日开盘涨幅 %d 行(open(S)/close(S-1))" % _n)
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
    warns = []
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
        if len(lines) > 1 and header.split(",") == CSV_HEADER:
            _yi = CSV_HEADER.index("yesterday_open_pct")
            _ai = CSV_HEADER.index("expected_auction_change_pct")
            _my = _ma = 0
            for _ln in lines[1:]:
                _cells = _ln.split(",")
                if len(_cells) > _yi and not (_cells[_yi] or "").strip():
                    _my += 1
                if len(_cells) > _ai and not (_cells[_ai] or "").strip():
                    _ma += 1
            if _my:
                warns.append("昨日开盘涨幅缺失/空行数=%d" % _my)
            if _ma:
                warns.append("预期开盘基准(exp_auc)缺失/空行数=%d" % _ma)
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
    if warns:
        print("[validate] 提醒(不阻上传):", "; ".join(warns))
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