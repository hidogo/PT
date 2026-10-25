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
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import bridge  # noqa: E402
import closeout_review as cr       # noqa: E402
import run_expectation_build as rb # noqa: E402
from bridge import axquant_contract as axc # noqa: E402

SCRIPT_VERSION = "v0.72"   # 运维小版（不改策略交易语义，strategy.py 仍 v0.71）


def _resolve_next_date(td: str, next_date: str) -> str:
    if next_date:
        return next_date.strip()
    d = datetime.date.fromisoformat(td)
    return bridge.calendar.next_trading_day(d).isoformat()


def _marker_path(out_root: str, trade_date: str) -> str:
    # 完成标记按日存放：计划任务兜底据此判定「复盘任务链是否已跑过」，避免重复复盘
    return os.path.join(out_root, "state", "oneclick_after_close_%s.done" % trade_date)


def _skip_if_done(out_root: str, trade_date: str, enabled: bool) -> bool:
    if not enabled:
        return False
    fp = _marker_path(out_root, trade_date)
    if os.path.isfile(fp):
        print("[oneclick] 当日完成标记已存在 -> 跳过（复盘任务链已跑过）：%s" % fp)
        return True
    return False


def _write_done_marker(out_root: str, trade_date: str, next_td: str, files: dict) -> None:
    try:
        fp = _marker_path(out_root, trade_date)
        _d = os.path.dirname(fp)
        if _d and not os.path.isdir(_d):
            os.makedirs(_d)
        payload = {
            "script": "run_one_click_after_close",
            "version": SCRIPT_VERSION,
            "trade_date": trade_date,
            "next_trade_date": next_td,
            "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "files": files,
        }
        tmp = fp + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp, fp)
        print("[oneclick] 完成标记: %s" % fp)
    except Exception as e:
        print("[oneclick] 写完成标记失败(不影响产出): %r" % e)


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
    p.add_argument("--no-selfwatch", action="store_true", help="关闭自选股同步（默认每个交易日收盘自动从客户端刷新）")
    p.add_argument("--skip-sync", action="store_true", help="跳过持仓同步（仅复盘+构建）")
    p.add_argument("--require-provider", action="store_true", help="missing provider input -> abort")
    p.add_argument("--api-dir", default="", help="PTradeQuantApi.py 所在目录")
    p.add_argument("--skip-if-done", action="store_true",
                   help="当日已完成(存在完成标记)则直接 rc=0 退出；供计划任务兜底，避免与复盘任务链重复运行")
    a = p.parse_args(argv)

    td = a.date or datetime.date.today().isoformat()
    next_td = _resolve_next_date(td, a.next_date)
    if not a.date:
        try:
            if not bridge.calendar.is_trading_day(datetime.date.fromisoformat(td)):
                print("[oneclick] %s 非交易日 -> 跳过（计划任务兜底不跑）" % td)
                return 0
        except Exception as e:
            print("[oneclick] 交易日历判定失败(继续): %r" % e)
    print("[oneclick] 收盘复盘日=%s 预期交易日(T+1)=%s source=%s out=%s"
          % (td, next_td, a.source or "(自动)", a.out_dir or bridge.PTRADE_BRIDGE_DIR))

    print("[oneclick] %s" % SCRIPT_VERSION)
    _out_root = a.out_dir or bridge.PTRADE_BRIDGE_DIR
    if _skip_if_done(_out_root, td, a.skip_if_done):
        return 0

    
    # 步骤0：数据提供方（AXquant）就绪校验 —— 前置显性化，避免读到陈旧/缺失输入
    print("[oneclick] 步骤0 提供方(AXquant)就绪校验 复盘日=%s 预期日=%s" % (td, next_td))
    axc.probe_report(td, next_td)
    _mw = axc.marker_warns(td, next_td)
    if _mw:
        print("[WARN] 预期链路断链（空 marker）: %s —— 预期 CSV 将缺失/为空，云端 expect_buy=0。请检查本地持仓桥接(QMT position_data.json)与 AXquant 复盘任务是否真正产出。" % "; ".join(_mw))
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
    _nrows = 0
    if os.path.isfile(_src_csv):
        try:
            with open(_src_csv, "r", encoding="utf-8") as _f:
                _nrows = max(sum(1 for _ in _f) - 1, 0)
        except Exception:
            _nrows = 0
    if os.path.isfile(_src_csv) and _nrows > 0:   # 护栏：新产 CSV 无数据行不覆盖既有 dated/latest
        with open(_src_csv, "rb") as _f:
            _cb = _f.read()
        for _fp in tuple(dict.fromkeys((_gen_csv, _latest_csv))):
            try:
                with open(_fp, "wb") as _f:
                    _f.write(_cb)
                print("[oneclick] %s -> %s" % (os.path.basename(_src_csv), os.path.basename(_fp)))
            except OSError as _e:
                print("[oneclick] 写 %s 失败: %r" % (_fp, _e))
    elif os.path.isfile(_src_csv):
        print("[oneclick] 新产预期 CSV 无数据行 -> 跳过 alias 覆盖（保护既有文件）")

    # 步骤4a: 自选股同步（默认执行；客户端未登录/无 XML 时保留既有文件并提示）
    if not a.no_selfwatch:
        try:
            import sync_selfwatch as ss
            ss.sync()
        except Exception as e:
            print("[oneclick] sync_selfwatch 失败(不影响预期/名单): %r" % e)

    # 步骤4: 导出 T-1 涨停/连板名单到同一待上传文件夹（upload_file, 供云端 _load_zt_lianban）
    try:
        import export_lianban
        export_lianban.run(a.date or None, None, a.out_dir or None,
                           alias="")
    except Exception as e:
        print("[oneclick] export_lianban 失败(不影响预期): %r" % e)
    # 步骤4b: 导出情绪冰点/回暖基线（T 日冰点+连续冰点天数，docs/40；供云端 _load_sentiment）
    try:
        import export_sentiment
        export_sentiment.run(a.date or None, a.out_dir or None)
    except Exception as e:
        print("[oneclick] export_sentiment 失败(不影响预期/名单): %r" % e)

    # 步骤5：产出一致性核对 —— 预期CSV vs 源jsonl, zt名单 vs 涨停池
    print("[oneclick] 步骤5 产出一致性核对 ...")
    _out = a.out_dir or bridge.PTRADE_BRIDGE_DIR
    _exp_csv = os.path.join(_out, "expectation_latest.csv")   # 云端实际消费的稳定指针
    # 一致性核对源：本地重建预期 JSONL 优先（本次链路=review 重建），其次显式 source / AXquant 侧预期
    _local_exp = bridge.expectation_store.default_expectation_path(next_td)
    _src = a.source or (_local_exp if os.path.isfile(_local_exp) else axc.paths(td, next_td)["expectation_source"])
    _fe = axc.check_expectation_consistency(_exp_csv, _src)
    print("  [预期] CSV=%s src=%s ok=%s %s" % (_fe["csv_codes"], _fe["src_codes"], _fe["ok"], _fe["note"]))
    _zt_csv = os.path.join(_out, "zt_lianban_latest.csv")
    _fz = axc.check_zt_consistency(_zt_csv, td)
    print("  [名单] zt=%s boards=%s date=%s ok=%s %s" % (_fz["zt_rows"], _fz["board_rows"], _fz["zt_date"], _fz["ok"], _fz["note"]))

    # 步骤6：待上传目录瘦身/归档（定时上传有数据限制：dated 只留最新 N 个，更早移入 archive/（非递归上传），archive 超期清理）
    try:
        import maintain_bridge_dir as _mbd
        _margv = ["--root", _out_dir] if a.out_dir else []
        _mbd.main(_margv)
    except Exception as _e:
        print("[oneclick] maintain_bridge_dir 失败(不影响预期/上传): %r" % _e)

    if rc == 0:
        _write_done_marker(_out, td, next_td, {
            "expectation_latest": _latest_csv,
            "expectation_t1": _src_csv,
            "zt_lianban_latest": _zt_csv,
            "sentiment_latest": os.path.join(_out, "sentiment_latest.csv"),
        })
    return rc


if __name__ == "__main__":
    raise SystemExit(main())