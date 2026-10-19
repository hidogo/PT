#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""收盘后一键总入口：同步持仓 -> 本地复盘 -> 预期 JSONL/CSV -> from-jsonl -> validate -> 待上传就绪。

把三段串成一次调用，避免盘中/收盘各自跑多个脚本：
  步骤1   sync_positions.run_sync()        拉当地收盘持仓 -> data/positions/positions_<date>.json
  步骤2   build_expectation_bridge.review   复盘 -> 预期 JSONL -> 待上传 CSV（数据侧兜底）
  步骤3   run_expectation_build.run_build   from-jsonl 复产 -> validate -> 报告待上传文件夹就绪

用法（收盘后、PTrade 客户端已登录连接；用 API 自带 Python3.7 保证 PTradeQuantApi 兼容）：
  "D:/gjzq/ptrade/Libs/Python/api/Libs/Python/python3/python.exe" ^
      run_one_click_after_close.py [--date 2026-10-16] [--next-date 2026-10-19]
可加：--logs <当日日志.txt>（采集 [seal]/[l2]/[may-order]）、--selfwatch（同步自选股）、
  --skip-sync（跳过持仓同步）、--source/--out-dir（透传给 from-jsonl）。
"""
from __future__ import annotations

import argparse
import datetime
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import bridge  # noqa: E402
import closeout_review as cr       # noqa: E402
import run_expectation_build as rb # noqa: E402
from bridge import axquant_contract as axc # noqa: E402


def _resolve_next_date(td: str, next_date: str) -> str:
    if next_date:
        return next_date.strip()
    d = datetime.date.fromisoformat(td)
    return bridge.calendar.next_trading_day(d).isoformat()


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="run_one_click_after_close",
        description="收盘后一键：同步持仓 -> 本地复盘 -> 预期桥接 CSV -> 校验 -> 待上传就绪",
    )
    p.add_argument("--date", default="", help="复盘日(收盘当日) YYYY-MM-DD，默认今日")
    p.add_argument("--next-date", default="", help="预期交易日 T+1，默认复盘日次日")
    p.add_argument("--source", default="", help="预期 position_expectation JSONL（from-jsonl 用，默认自动兜底）")
    p.add_argument("--out-dir", default="", help="待上传 CSV 根目录（默认 PTRADE_BRIDGE_DIR）")
    p.add_argument("--logs", default="", help="当日交易日志 .txt -> 解析 [seal]/[l2]/[may-order]")
    p.add_argument("--selfwatch", action="store_true", help="步骤0 同步自选股")
    p.add_argument("--skip-sync", action="store_true", help="跳过持仓同步（仅复盘+构建）")
    p.add_argument("--require-provider", action="store_true", help="missing provider input -> abort")
    p.add_argument("--api-dir", default="", help="PTradeQuantApi.py 所在目录")
    a = p.parse_args(argv)

    td = a.date or datetime.date.today().isoformat()
    next_td = _resolve_next_date(td, a.next_date)
    print("[oneclick] 收盘复盘日=%s 预期交易日(T+1)=%s source=%s out=%s"
          % (td, next_td, a.source or "(自动)", a.out_dir or bridge.PTRADE_BRIDGE_DIR))

    
    # 步骤0：数据提供方（AXquant）就绪校验 —— 前置显性化，避免读到陈旧/缺失输入
    print("[oneclick] 步骤0 提供方(AXquant)就绪校验 复盘日=%s 预期日=%s" % (td, next_td))
    axc.probe_report(td, next_td)
    _miss = axc.missing(td, next_td)
    if _miss:
        print("[oneclick] 提供方缺失输入: %s" % ", ".join(_miss))
        if a.require_provider:
            print("[oneclick] --require-provider 已置 -> 中止")
            return 2
        print("[oneclick] 警告：以上缺失将导致复盘/名单为空，继续(--require-provider 可强制中止)")

# 1+2: 收盘复盘（同步持仓可选 + 复盘 + 预期 CSV）。closeout_review.main() 返回退出码。
    cr_args = []
    if a.date:
        cr_args += ["--date", a.date]
    if a.next_date:
        cr_args += ["--next-date", a.next_date]
    if a.logs:
        cr_args += ["--logs", a.logs]
    if a.out_dir:
        cr_args += ["--out-dir", a.out_dir]
    if a.api_dir:
        cr_args += ["--api-dir", a.api_dir]
    if a.selfwatch:
        cr_args += ["--selfwatch"]
    if a.skip_sync:
        cr_args += ["--skip-sync"]
    rc = cr.main(cr_args)
    if rc != 0:
        print("[oneclick] closeout_review 退出码=%d —— 复盘/预期 CSV 未就绪，停止后续。" % rc)
        return rc

    # 3: from-jsonl + validate（复产 CSV + 校验 + 待上传就绪报告）
    print("[oneclick] 步骤3 构建+校验预期桥接 CSV ->")
    rc = rb.run_build(next_td, a.source, a.out_dir or "")
    _out_dir = a.out_dir or bridge.PTRADE_BRIDGE_DIR
    _src_csv = os.path.join(_out_dir, "expectation_%s.csv" % next_td)   # 内部产出的交易日文件
    _gen_csv = os.path.join(_out_dir, "expectation_%s.csv" % td)        # 生成日期命名（以生成日期为准）
    _latest_csv = os.path.join(_out_dir, "expectation_latest.csv")      # 稳定指针（云端优先读）
    if os.path.isfile(_src_csv):
        with open(_src_csv, "rb") as _f:
            _cb = _f.read()
        for _fp in tuple(dict.fromkeys((_gen_csv, _latest_csv))):
            try:
                with open(_fp, "wb") as _f:
                    _f.write(_cb)
                print("[oneclick] %s -> %s" % (os.path.basename(_src_csv), os.path.basename(_fp)))
            except OSError as _e:
                print("[oneclick] 写 %s 失败: %r" % (_fp, _e))

    # 步骤4: 导出 T-1 涨停/连板名单到同一待上传文件夹（upload_file, 供云端 _load_zt_lianban）
    try:
        import export_lianban
        export_lianban.run(a.date or None, None, a.out_dir or None,
                           alias="")
    except Exception as e:
        print("[oneclick] export_lianban 失败(不影响预期): %r" % e)

    # 步骤5：产出一致性核对 —— 预期CSV vs 源jsonl, zt名单 vs 涨停池
    print("[oneclick] 步骤5 产出一致性核对 ...")
    import os
    _out = a.out_dir or bridge.PTRADE_BRIDGE_DIR
    _exp_csv = os.path.join(_out, "expectation_latest.csv")   # 云端实际消费的稳定指针
    _src = a.source or axc.paths(td, next_td)["expectation_source"]
    _fe = axc.check_expectation_consistency(_exp_csv, _src)
    print("  [预期] CSV=%s src=%s ok=%s %s" % (_fe["csv_codes"], _fe["src_codes"], _fe["ok"], _fe["note"]))
    _zt_csv = os.path.join(_out, "zt_lianban_latest.csv")
    _fz = axc.check_zt_consistency(_zt_csv, td)
    print("  [名单] zt=%s boards=%s date=%s ok=%s %s" % (_fz["zt_rows"], _fz["board_rows"], _fz["zt_date"], _fz["ok"], _fz["note"]))

    return rc


if __name__ == "__main__":
    raise SystemExit(main())