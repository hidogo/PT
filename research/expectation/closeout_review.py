#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""收盘后一键复盘流程：同步持仓 -> 本地复盘（open_reason+持仓+涨停池+洞察）-> 预期 CSV。

融合复盘流程内（对应 docs/26 本地运行侧 + docs/27 持仓同步）：
  步骤1  sync_positions.run_sync()  拉当地收盘持仓 -> data/positions/positions_<date>.json
  步骤2  build_expectation_bridge.review  复盘 -> 预期 JSONL -> 待上传 CSV
    （未传 --positions 时默认读步骤1同步产出的 positions_<date>.json）

用法（先登录并连接 PTrade 客户端；用 API 自带 Python3.7 以保证 PTradeQuantCore.pyd 兼容）:
  "D:/gjzq/ptrade/Libs/Python/api/Libs/Python/python3/python.exe" ^
     D:\PROJ\PT\research\expectation\closeout_review.py --date 2026-10-16 --logs <当日日志.txt>
         注：--logs 可选，解析 [seal]/[l2]/[may-order] 到 data/logs 供对账与阈值回归。
"""
from __future__ import annotations

import argparse
import datetime
import os
import sys
import types

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import build_expectation_bridge as be  # noqa: E402
import log_collector as lc             # noqa: E402
import sync_positions as sp            # noqa: E402


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="closeout_review",
                                description="收盘后一键：同步持仓 -> 本地复盘 -> 预期 CSV")
    p.add_argument("--date", default="", help="复盘日(收盘当日) YYYY-MM-DD，默认今日")
    p.add_argument("--next-date", default="", help="预期交易日 T+1，默认复盘日次日")
    p.add_argument("--open-reason", default="", help="open_reason JSONL（默认本地/AXquant 兜底）")
    p.add_argument("--snapshots", default="", help="涨停池快照 JSON（默认本地/AXquant 兜底）")
    p.add_argument("--insights", default="", help="复盘洞察 JSON（可选）")
    p.add_argument("--positions", default="", help="持仓 JSON（可选；默认用步骤1同步产物）")
    p.add_argument("--out-dir", default="", help="待上传 CSV 输出目录（默认 PTRADE_BRIDGE_DIR）")
    p.add_argument("--skip-sync", action="store_true", help="跳过持仓同步（仅复盘）")
    p.add_argument("--logs", default="", help="当日交易日志 .txt（粘贴保存）-> 解析 [seal]/[l2]/[may-order] 到 data/logs")
    p.add_argument("--selfwatch", action="store_true", help="步骤0同步：客户端自选股 -> 上传暂存 selfwatch.csv")
    p.add_argument("--api-dir", default=sp.API_DIR, help="PTradeQuantApi.py 所在目录")
    a = p.parse_args(argv)

    td = a.date or datetime.date.today().isoformat()
    if a.selfwatch:
        print("== [closeout] 步骤0 同步自选股(客户端->上传暂存) ==")
        try:
            import sync_selfwatch as ss
            ss.sync()
        except Exception as exc:
            print("[closeout] 自选股同步失败(可跳过): %s" % exc, file=sys.stderr)
    if a.logs:
        print("== [closeout] 步骤0 采集交易日志 [seal]/[l2] ==")
        try:
            lc.ingest(a.logs, td)
            lc.summary(td)
        except Exception as exc:
            print("[closeout] 日志采集失败(可跳过): %s" % exc, file=sys.stderr)
    if not a.skip_sync:
        print("== [closeout] 步骤1 同步收盘持仓 ==")
        try:
            sp.run_sync(date=td, out=a.positions, api_dir=a.api_dir)
        except Exception as exc:
            print("[closeout] 同步持仓失败(可跳过): %s" % exc, file=sys.stderr)
    else:
        print("== [closeout] 步骤1 跳过持仓同步 (--skip-sync) ==")

    print("== [closeout] 步骤2 本地复盘 -> 预期 CSV ==")
    rv_args = types.SimpleNamespace(
        date=td,
        next_date=a.next_date or "",
        open_reason=a.open_reason,
        snapshots=a.snapshots,
        positions=a.positions or "",
        insights=a.insights,
        review_out="",
        expectation_out="",
        out_dir=a.out_dir or "",
    )
    rc = be.cmd_review(rv_args)
    print("== [closeout] 完成 ==")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())