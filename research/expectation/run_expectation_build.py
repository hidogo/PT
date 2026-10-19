#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一键桥接预期 CSV 构建+校验（from-jsonl -> validate -> 待上传文件夹就绪）。

并入「本地复盘/预期 -> 上传」收盘/盘前一键流程，安排在
  sync_positions / closeout_review（生成 position_expectation_<T+1>.jsonl）
  之后、Ptrade「定时上传」之前运行。

用法:
  python run_expectation_build.py [--date YYYY-MM-DD] [--source 预期.jsonl] [--out-dir 目录]

默认日期 = 下一交易日（收盘跑=次日 T+1；盘前跑=当日 T+1）。
默认 source = bridge.default_expectation_path(T+1)；缺失兜底 AXquant 的
  position_expectation_<T+1>.jsonl；再缺则 from-jsonl 报错退出。

产物:
  <out-dir>/expectation_<T+1>.csv        待上传根（定时上传=按文件夹识别）
  <out-dir>/archive/expectation_<T+1>.csv.meta.json + ptrade_today.csv（不上传）
脚本本身不代传网络；保证文件新鲜+校验通过后，由 Ptrade 客户端「定时上传」绑定文件夹触发上送。
"""
from __future__ import annotations

import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import bridge  # noqa: E402
import build_expectation_bridge as beb  # noqa: E402


def _resolve_default_date(text: str) -> str:
    if text:
        return text.strip()
    from datetime import date
    return bridge.calendar.next_trading_day(date.today()).isoformat()


def run_build(td: str, source: str = "", out_dir: str = "") -> int:
    """from-jsonl -> validate -> 打印待上传文件夹就绪。返回进程退出码。"""
    be_args = argparse.Namespace(date=td, source=source, out_dir=out_dir, keep_days=1)
    rc = beb.cmd_from_jsonl(be_args)
    if rc != 0:
        print("[build] from-jsonl 退出码=%d —— 未生成/刷新待上传 CSV，跳过校验与上传。" % rc)
        return rc

    va_args = argparse.Namespace(date=td, out_dir=out_dir)
    rc2 = beb.cmd_validate(va_args)
    if rc2 != 0:
        print("[build] validate 未通过退出码=%d（见上方原因；缺失基准仅提醒不阻上传）。" % rc2)
        return rc2

    root = (out_dir or "").strip() or bridge.PTRADE_BRIDGE_DIR
    csv_path = os.path.join(root, "expectation_%s.csv" % td)
    print("[build] 待上传文件夹就绪:")
    print("  上传文件夹 :", root)
    print("  当天 CSV   :", csv_path)
    print("  识别规则   : 定时上传=按文件夹，云端消费 expectation_<交易日期>.csv")
    print("  下一步     : 在 Ptrade 客户端「定时上传」绑定该文件夹触发上送（本脚本不代传）。")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="run_expectation_build",
        description="一键构建+校验预期桥接 CSV（from-jsonl -> validate -> 待上传文件夹就绪）",
    )
    p.add_argument("--date", default="", help="YYYY-MM-DD，默认=下一交易日")
    p.add_argument("--source", default="", help="预期 position_expectation JSONL，默认自动兜底")
    p.add_argument("--out-dir", default="", help="待上传根目录，默认 PTRADE_BRIDGE_DIR")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    td = _resolve_default_date(args.date)
    print("[run] 桥接日期=%s source=%s out=%s" % (td, args.source or "(自动)", args.out_dir or bridge.PTRADE_BRIDGE_DIR))
    return run_build(td, args.source, args.out_dir)


if __name__ == "__main__":
    raise SystemExit(main())