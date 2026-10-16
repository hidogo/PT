#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地收盘后从 PTrade 客户端同步持仓到本地 JSON（供复盘/预期 review --positions 消费）。

方案：PTrade 客户端侧 API（docs/22）—— get_engine() 建连 -> get_positions() 拉全部持仓，
收盘后仍可查（持仓/可用数量是账户侧数据，不依赖盘中行情）。与 AXquant 走 QMT 桥不同。

用法（先启动并登录 PTrade 客户端且已连接服务端；用 API 自带 Python3.7）:
  "D:/gjzq/ptrade/Libs/Python/api/Libs/Python/python3/python.exe" sync_positions.py [--date 2026-10-16]

输出: D:/PROJ/PT/data/positions/positions_<date>.json
      包装 {positions:[{code,name,amount,enable_amount,cost,last,market_value}], portfolio, ...}
代码口径: 统一为 AXquant 的 .SH/.SZ/.BJ（数字前缀推断 + 后缀映射），与 bridge/publish.normalize_code 兼容。
run_sync() 供 closeout_review.py 一键流程复用。
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

API_DIR = r"D:/gjzq/ptrade/Libs/Python/api"
_HERE = os.path.dirname(os.path.abspath(__file__))          # .../research/expectation
_PT_ROOT = os.path.dirname(os.path.dirname(_HERE))           # .../PT
DEFAULT_OUT = os.path.join(_PT_ROOT, "data", "positions")


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
    return {
        "code": _norm_symbol(raw),
        "symbol": raw,
        "name": str(_get(pos, "name", "") or ""),
        "amount": int(_get(pos, "amount", 0) or 0),
        "enable_amount": int(_get(pos, "enable_amount", 0) or 0),
        "cost": float(_get(pos, "cost_basis", 0.0) or 0.0),
        "last": float(_get(pos, "last_sale_price", 0.0) or 0.0),
        "market_value": float(_get(pos, "market_value", 0.0) or 0.0),
    }


def _ensure_parent(path: str) -> None:
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)


def run_sync(date: str = "", out: str = "", api_dir: str = API_DIR):
    """连接 PTrade 客户端拉全部持仓并写本地 JSON，返回 (payload, out_path)。"""
    td = date or datetime.date.today().isoformat()
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

    out_path = out or os.path.join(DEFAULT_OUT, "positions_%s.json" % td)
    _ensure_parent(out_path)
    payload = {
        "trade_date": td,
        "source": "ptrade_quant_api",
        "positions": records,
        "portfolio": portfolio,
        "synced_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    tmp = out_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, out_path)

    print("synced positions=%d date=%s" % (len(records), td))
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