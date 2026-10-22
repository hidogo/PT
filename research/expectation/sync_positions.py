#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地收盘后从 PTrade 客户端同步持仓到本地 JSON（供复盘/预期 review --positions 消费）。

方案：PTrade 客户端侧 API（docs/22）—— get_engine() 建连 -> get_positions() 拉全部持仓，
收盘后仍可查（持仓/可用数量是账户侧数据，不依赖盘中行情）。与 AXquant 走 QMT 桥不同。

稳定性（2026-10-22 起）：API 调用带守护线程超时（单次 25s、最多 2 次），清算期 zeromq
空结果/挂起不再卡死进程；失败或空结果自动回退读 PTrade 手工导出
D:/PROJ/PT/data/export/Hold_YYYYMMDD.csv（GBK，表头即空仓，不存在时取最新 Hold_*.csv），
positions JSON 的 source 标记 ptrade_quant_api / ptrade_export_fallback。

用法（先启动并登录 PTrade 客户端且已连接服务端；用 API 自带 Python3.7）:
  "D:/gjzq/ptrade/Libs/Python/api/Libs/Python/python3/python.exe" sync_positions.py [--date 2026-10-16]

输出: D:/PROJ/PT/data/positions/positions_<date>.json
      包装 {positions:[{code,name,amount,enable_amount,cost,last,market_value}], portfolio, ...}
代码口径: 统一为 AXquant 的 .SH/.SZ/.BJ（数字前缀推断 + 后缀映射），与 bridge/publish.normalize_code 兼容。
run_sync() 供 closeout_review.py 一键流程复用。
"""
from __future__ import annotations

import argparse
import csv
import datetime
import io
import json
import os
import sys

API_DIR = r"D:/gjzq/ptrade/Libs/Python/api"
_HERE = os.path.dirname(os.path.abspath(__file__))          # .../research/expectation
_PT_ROOT = os.path.dirname(os.path.dirname(_HERE))           # .../PT
DEFAULT_OUT = os.path.join(_PT_ROOT, "data", "positions")
EXPORT_DIR = os.path.join(_PT_ROOT, "data", "export")


def _norm_symbol(sym: str) -> str:
    s = str(sym or "").strip()
    if not s:
        return ""
    lower = s.lower()
    num = s.split(".")[0]
    head = num[:1]
    if lower.endswith(".xshg") or head in ("5", "6", "9"):
        return num + ".SH"
    if lower.endswith(".xshe") or head in ("0", "1", "2", "3"):
        return num + ".SZ"
    if lower.endswith(".xbj") or head in ("4", "8"):
        return num + ".BJ"
    return num


def _get(pos, name, default=0.0):
    try:
        return getattr(pos, name)
    except Exception:
        try:
            return pos[name]
        except Exception:
            return default


def _record(pos) -> dict:
    raw = str(_get(pos, "symbol", "") or "")
    amount = int(_get(pos, "amount", 0) or 0)
    enable = int(_get(pos, "enable_amount", 0) or 0)
    return {
        "code": _norm_symbol(raw),
        "symbol": raw,
        "name": str(_get(pos, "name", "") or ""),
        "amount": amount,
        "volume": amount,
        "enable_amount": enable,
        "cost": float(_get(pos, "cost_basis", 0.0) or 0.0),
        "last": float(_get(pos, "last_sale_price", 0.0) or 0.0),
        "market_value": float(_get(pos, "market_value", 0.0) or 0.0),
    }


def _ensure_parent(path: str) -> None:
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)


def _api_fetch_once(api_dir: str):
    """单次调用 PTrade 客户端 API 拉全部持仓与组合净值。"""
    sys.path.insert(0, api_dir)
    from PTradeQuantApi import get_portfolio, get_positions  # noqa: E402

    pos_map = get_positions() or {}
    records = []
    for code, pos in pos_map.items():
        r = _record(pos)
        r["raw_code"] = str(code)
        if r["code"]:
            records.append(r)
        else:
            print("skip unresolvable position:", code, file=sys.stderr)

    portfolio = {}
    try:
        pf = get_portfolio()
        for name in ("cash", "positions_value", "portfolio_value"):
            portfolio[name] = float(_get(pf, name, 0.0) or 0.0)
    except Exception as exc:
        print("portfolio query failed:", exc, file=sys.stderr)
    return records, portfolio


def _api_fetch_bounded(api_dir: str, attempts: int = 2, timeout_sec: float = 25.0):
    """有界调用 PTrade API：守护线程 + join 超时，清算期 zeromq 挂起不阻塞进程。"""
    import threading
    import time

    for i in range(1, attempts + 1):
        box = {}
        def _run():
            try:
                box["records"], box["portfolio"] = _api_fetch_once(api_dir)
            except Exception as exc:
                box["error"] = repr(exc)
        t = threading.Thread(target=_run, daemon=True, name="ptrade-sync")
        t.start()
        t.join(timeout_sec)
        if not t.is_alive():
            if "error" not in box:
                return box.get("records", []), box.get("portfolio", {})
            print("[sync] PTrade API 第 %d/%d 次失败: %s"
                  % (i, attempts, box["error"]), file=sys.stderr)
        else:
            print("[sync] PTrade API 第 %d/%d 次调用超时(>%ss)，已放弃等待"
                  % (i, attempts, timeout_sec), file=sys.stderr)
        if i < attempts:
            time.sleep(2)
    return [], {}


def _parse_export_csv(path: str):
    """解析 PTrade 手工导出持仓 CSV（GBK 优先），按证券代码聚合多账户行。"""
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except OSError as exc:
        print("读取持仓导出失败: %r" % exc, file=sys.stderr)
        return None
    text = None
    for enc in ("utf-8-sig", "gb18030", "gbk"):
        try:
            text = raw.decode(enc)
            break
        except (UnicodeDecodeError, LookupError):
            continue
    if text is None:
        print("持仓导出编码无法识别: %s" % path, file=sys.stderr)
        return None
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return None
    header = [str(h).strip() for h in rows[0]]
    idx = {name: i for i, name in enumerate(header) if name}
    def _col(*names):
        for n in names:
            if n in idx:
                return idx[n]
        return -1
    i_code = _col("证券代码", "代码", "symbol")
    i_name = _col("证券名称", "名称", "name")
    i_amount = _col("持有数量", "持股数量", "持仓数量", "amount")
    i_enable = _col("可用数量", "可用股数", "可卖数量", "enable_amount")
    i_cost = _col("成本价", "买入成本", "持仓成本", "cost")
    i_mv = _col("证券市值", "市值", "market_value")
    if i_code < 0 or i_amount < 0:
        print("持仓导出缺少必要列(证券代码/持有数量): %s" % path, file=sys.stderr)
        return None
    def _num(row, i):
        if i < 0 or i >= len(row):
            return 0.0
        v = str(row[i]).strip().replace(",", "")
        if not v:
            return 0.0
        try:
            return float(v)
        except ValueError:
            return 0.0
    agg = {}
    for row in rows[1:]:
        if not row:
            continue
        sym = str(row[i_code]).strip()
        if not sym:
            continue
        amount = int(_num(row, i_amount))
        if amount <= 0:
            continue
        code = _norm_symbol(sym)
        if not code:
            continue
        name = str(row[i_name]).strip() if 0 <= i_name < len(row) else ""
        enable = int(_num(row, i_enable))
        cost = _num(row, i_cost)
        mv = _num(row, i_mv)
        a = agg.get(code)
        if a is None:
            a = {"code": code, "symbol": sym, "name": name, "amount": 0,
                 "enable_amount": 0, "cost": 0.0, "last": 0.0,
                 "market_value": 0.0, "cost_amt": 0.0}
            agg[code] = a
        a["amount"] += amount
        a["enable_amount"] += enable
        a["market_value"] += mv
        if cost > 0:
            a["cost_amt"] += cost * amount
        if not a["name"] and name:
            a["name"] = name
    records = []
    for code in sorted(agg):
        a = agg[code]
        if a["amount"] > 0 and a["cost_amt"] > 0:
            a["cost"] = round(a["cost_amt"] / a["amount"], 4)
        if a["amount"] > 0 and a["market_value"] > 0:
            a["last"] = round(a["market_value"] / a["amount"], 4)
        elif a["amount"] > 0 and a["cost"] > 0:
            a["last"] = a["cost"]
        a.pop("cost_amt", None)
        a["volume"] = a["amount"]
        records.append(a)
    return records


def _fallback_export_positions(td: str):
    """回退读 PTrade 导出持仓：优先 Hold_YYYYMMDD.csv，其次最新 Hold_*.csv。"""
    cands = []
    if td:
        cands.append(os.path.join(EXPORT_DIR, "Hold_%s.csv" % td.replace("-", "")))
    try:
        names = [n for n in os.listdir(EXPORT_DIR)
                 if n.startswith("Hold_") and n.endswith(".csv")]
    except OSError:
        names = []
    for n in sorted(names, reverse=True):
        p = os.path.join(EXPORT_DIR, n)
        if p not in cands:
            cands.append(p)
    for path in cands:
        if not os.path.isfile(path):
            continue
        records = _parse_export_csv(path)
        if records is None:
            continue
        return records, path
    return [], ""


def run_sync(date: str = "", out: str = "", api_dir: str = API_DIR):
    """连接 PTrade 客户端拉全部持仓并写本地 JSON，返回 (payload, out_path)。

    API 空/超时自动回退 D:/PROJ/PT/data/export/Hold_<date>.csv（表头即空仓），
    避免清算期 zeromq 卡死；回退后 source=ptrade_export_fallback。
    """
    td = date or datetime.date.today().isoformat()
    records, portfolio = _api_fetch_bounded(api_dir)
    source = "ptrade_quant_api"
    export_path = ""
    if not records:
        records, export_path = _fallback_export_positions(td)
        if export_path:
            source = "ptrade_export_fallback"
            print("[sync] 使用导出 CSV 回退（API 空/失败）: %s" % export_path, file=sys.stderr)
        else:
            source = "ptrade_api_empty"
            print("[sync] PTrade API 空且无导出 CSV 回退，按空持仓处理", file=sys.stderr)

    out_path = out or os.path.join(DEFAULT_OUT, "positions_%s.json" % td)
    _ensure_parent(out_path)
    payload = {
        "trade_date": td,
        "source": source,
        "fallback_export": export_path,
        "positions": records,
        "portfolio": portfolio,
        "synced_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    tmp = out_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, out_path)

    print("synced positions=%d date=%s source=%s" % (len(records), td, source))
    for r in records:
        print("  - %s %s qty=%d/%d cost=%.3f last=%.3f" %
              (r["code"], r["name"], r["enable_amount"], r["amount"], r["cost"], r["last"]))
    print("portfolio:", portfolio)
    print("->", out_path)
    return payload, out_path


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="本地收盘后同步 PTrade 持仓到本地 JSON")
    p.add_argument("--date", default="", help="YYYY-MM-DD")
    p.add_argument("--out", default="", help="输出文件（默认 data/positions/positions_<date>.json）")
    p.add_argument("--api-dir", default=API_DIR, help="PTradeQuantApi.py 所在目录")
    a = p.parse_args(argv)
    run_sync(date=a.date, out=a.out, api_dir=a.api_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
