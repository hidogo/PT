#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""任意时刻一键探活 + 产出一致性核验（数据提供方 AXquant）。

用法：
  python verify_provider.py [--date 2026-10-16] [--next-date 2026-10-19]
      [--source <预期jsonl>] [--bridge-dir <待上传目录>] [--strict]

- 步骤A 提供方就绪：逐条探活 AXquant 输入（复盘/开板/特快照/涨停池/预期源 + PT 镜像）
- 步骤B 产出一致性：预期 CSV ↔ 源 jsonl、涨停名单 ↔ 涨停池
- --strict：存在缺失输入或一致性不一致时返回非零退出码（便于脚本门禁）
尚未跑复盘链时也能用：预期 CSV 缺则提示，不停机。
"""
from __future__ import annotations

import argparse
import datetime
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import bridge  # noqa: E402
from bridge import axquant_contract as axc  # noqa: E402


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="verify_provider", description="AXquant 提供方探活 + 产出一致性核验")
    p.add_argument("--date", default="", help="复盘日 YYYY-MM-DD，默认今日")
    p.add_argument("--next-date", default="", help="预期日 T+1，默认按交易日历推")
    p.add_argument("--source", default="", help="预期 position_expectation jsonl，默认走数据契约")
    p.add_argument("--bridge-dir", default="", help="待上传目录，默认 PTRADE_BRIDGE_DIR")
    p.add_argument("--strict", action="store_true", help="存在缺失/不一致时返回非零")
    a = p.parse_args(argv)

    td = a.date or datetime.date.today().isoformat()
    if a.next_date:
        nt = a.next_date.strip()
    else:
        nt = bridge.calendar.next_trading_day(datetime.date.fromisoformat(td)).isoformat()
    root = (a.bridge_dir or "").strip() or bridge.PTRADE_BRIDGE_DIR

    problems = []
    print("== 步骤A 提供方就绪探活 复盘日=%s 预期日=%s ==" % (td, nt))
    axc.probe_report(td, nt)
    miss = axc.missing(td, nt)
    if miss:
        print("  缺失输入: %s" % ", ".join(miss))
        problems += ["missing:%s" % m for m in miss]
    else:
        print("  缺省 OK")

    print("== 步骤B 产出一致性核对 ==")
    exp_csv = os.path.join(root, "expectation_%s.csv" % nt)
    src = a.source or axc.paths(td, nt)["expectation_source"]
    if os.path.isfile(exp_csv) and os.path.isfile(src):
        fe = axc.check_expectation_consistency(exp_csv, src)
        print("  [预期] CSV=%s src=%s ok=%s %s" % (fe["csv_codes"], fe["src_codes"], fe["ok"], fe["note"]))
        if not fe["ok"]:
            problems.append("expectation-consistency")
    else:
        print("  [预期] 缺产物/源(CSV=%s 存在=%s | src=%s 存在=%s) —— 尚未跑复盘链则属正常"
              % (os.path.basename(exp_csv), os.path.isfile(exp_csv), os.path.basename(src), os.path.isfile(src)))

    zt_csv = os.path.join(root, "zt_lianban_latest.csv")
    if os.path.isfile(zt_csv):
        fz = axc.check_zt_consistency(zt_csv, td)
        print("  [名单] zt=%s boards=%s date=%s ok=%s %s" % (fz["zt_rows"], fz["board_rows"], fz["zt_date"], fz["ok"], fz["note"]))
        if not fz["ok"]:
            problems.append("zt-lianban-consistency")
    else:
        print("  [名单] 未找到 %s —— 跑 export_lianban / 一键收盘步骤4" % zt_csv)

    print("== 结论: %s ==" % ("通过" if not problems else "存在问题: %s" % ", ".join(problems)))
    return 1 if (a.strict and problems) else 0


if __name__ == "__main__":
    raise SystemExit(main())