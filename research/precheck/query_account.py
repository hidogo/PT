#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""账户资金探针（第 1 步：确认模拟账户初始资金）。

连接已登录的 PTrade 客户端，读取 Portfolio（cash/positions_value/portfolio_value 等全部字段）
与全部持仓，打印并落 JSON 到 data/positions/query_account_<date>.json。
用法（客户端已启动并登录；用 API 自带 Python3.7）:
  "D:/gjzq/ptrade/Libs/Python/api/Libs/Python/python3/python.exe" ^
      research/precheck/query_account.py [--api-dir D:/gjzq/ptrade/Libs/Python/api]
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys


def _attr(obj, name, default=None):
    try:
        return getattr(obj, name)
    except Exception:
        try:
            return obj[name]
        except Exception:
            return default


def _public(obj) -> dict:
    """dump 对象全部非下划线属性（含实际字段名，供对齐云端消费字段）。"""
    out = {}
    if obj is None:
        return out
    if isinstance(obj, dict):
        for k, v in obj.items():
            out[str(k)] = v
        return out
    for name in dir(obj):
        if name.startswith("_"):
            continue
        try:
            v = getattr(obj, name)
            if not callable(v):
                out[name] = v
        except Exception:
            continue
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="账户资金探针：Portfolio + 持仓全字段")
    p.add_argument("--api-dir", default=r"D:/gjzq/ptrade/Libs/Python/api")
    p.add_argument("--out", default="", help="输出 JSON（默认 data/positions/query_account_<date>.json）")
    a = p.parse_args(argv)

    sys.path.insert(0, a.api_dir)
    try:
        from PTradeQuantApi import get_portfolio, get_positions
    except Exception as e:
        print("API 导入失败：%r（确认 api-dir 正确）" % e, file=sys.stderr)
        return 2

    try:
        pf = get_portfolio()
    except Exception as e:
        print("get_portfolio 失败：%r（客户端未登录/未连接？）" % e, file=sys.stderr)
        return 2

    pf_all = _public(pf)
    cash = pf_all.get("cash", 0.0)
    pv = pf_all.get("positions_value", 0.0)
    total = pf_all.get("portfolio_value", 0.0)

    positions = {}
    try:
        pos_map = get_positions() or {}
        for code, pos in pos_map.items():
            d = _public(pos)
            d["raw_code"] = str(code)
            positions[str(code)] = d
    except Exception as e:
        print("get_positions 失败：%r" % e, file=sys.stderr)

    td = datetime.date.today().isoformat()
    payload = {
        "trade_date": td,
        "probe": "query_account",
        "portfolio": pf_all,
        "portfolio_summary": {
            "cash": float(cash or 0.0),
            "positions_value": float(pv or 0.0),
            "portfolio_value": float(total or 0.0),
        },
        "positions": positions,
        "queried_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }

    print("== 账户资金探针 ==")
    print("总资产 portfolio_value = %.2f" % (float(total or 0.0)))
    print("可用资金 cash          = %.2f" % (float(cash or 0.0)))
    print("持仓市值 positions_value= %.2f" % (float(pv or 0.0)))
    print("持仓只数               = %d" % len(positions))
    print("-- Portfolio 全部字段 --")
    for k, v in pf_all.items():
        print("  %-20s = %r" % (k, v))
    for code, d in positions.items():
        print("-- 持仓 %s --" % code)
        for k, v in d.items():
            print("  %-20s = %r" % (k, v))

    out_path = a.out or os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "data", "positions", "query_account_%s.json" % td)
    parent = os.path.dirname(out_path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    tmp = out_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
    os.replace(tmp, out_path)
    print("->", out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
