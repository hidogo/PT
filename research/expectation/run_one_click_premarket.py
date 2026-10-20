#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""盘前一键：生成今日待上传文件 + 校验 + 上传勾选清单（无需登录，不重跑收盘复盘）。

T-1 收盘已跑过 run_one_click_after_close 生成 position_expectation_<T>.jsonl 的前提下，
T 日 09:20 前运行本脚本把今日供给就位并打印上传勾选：
  步骤0  提供方(AXquant)就绪探活            axc.probe_report / missing
  步骤1  生成预期 CSV                        expectation_<T>.csv + latest（复用 run_expectation_build）
  步骤2  生成涨停/连板名单                    zt_lianban_latest.csv（T-1 数据，复用 export_lianban）
  步骤3  产出一致性核对                      预期 CSV<->源 jsonl；名单<->涨停池
  步骤4  上传勾选清单                        本地文件 -> 云端落点 -> 盘中核对关键字

护栏：
  - 「空仓 marker」源（record_type=position_expectation_marker）视为正常无预期，不上传、不覆盖既有文件；
  - 预期 CSV 无数据行时不覆盖既有 dated/latest（防把好文件冲成空表）。

用法（本机 Python3.10，无需登录 PTrade）：
  python run_one_click_premarket.py [--date 复盘日T-1] [--next-date 验证日T] [--out-dir 待上传根]
默认：复盘日=上一交易日，验证日=今日（今日非交易日则取下一交易日）。
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
import run_expectation_build as rb  # noqa: E402
from bridge import axquant_contract as axc  # noqa: E402


def _resolve_defaults(td: str, nt: str) -> tuple:
    today = datetime.date.today()
    if td:
        d_td = datetime.date.fromisoformat(td)
    else:
        d_td = bridge.calendar.previous_trading_day(today)
    if nt:
        d_nt = datetime.date.fromisoformat(nt)
    else:
        d_nt = today if bridge.calendar.is_trading_day(today) else bridge.calendar.next_trading_day(today)
    return d_td.isoformat(), d_nt.isoformat()


def _rows_of(path: str) -> int:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return max(sum(1 for _ in f) - 1, 0)
    except Exception:
        return -1


def _source_is_empty_marker(path: str) -> bool:
    """源 JSONL 是否为「空仓 marker」（position_expectation_marker，无实际预期）。"""
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
                    return False
                return str(rec.get("record_type") or "") == "position_expectation_marker"
        return False
    except Exception:
        return False


def _copy_alias(src_csv: str, gen_csv: str, latest_csv: str) -> None:
    """rb.run_build 产出的 验证日 命名 -> 生成日命名 + latest 稳定指针（与收盘一键同规则）。
    护栏：新产 CSV 无数据行时不覆盖既有 dated/latest。"""
    if not os.path.isfile(src_csv):
        return
    if _rows_of(src_csv) <= 0:
        print("[premarket] 新产预期 CSV 无数据行 -> 跳过 alias 覆盖（保护既有文件）")
        return
    with open(src_csv, "rb") as _f:
        _cb = _f.read()
    for _fp in tuple(dict.fromkeys((gen_csv, latest_csv))):
        try:
            with open(_fp, "wb") as _f:
                _f.write(_cb)
            print("[premarket] %s -> %s" % (os.path.basename(src_csv), os.path.basename(_fp)))
        except OSError as _e:
            print("[premarket] 写 %s 失败: %r" % (_fp, _e))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="run_one_click_premarket",
        description="盘前一键：生成今日待上传文件 + 校验 + 上传勾选清单",
    )
    p.add_argument("--date", default="", help="复盘日(T-1) YYYY-MM-DD，默认上一交易日")
    p.add_argument("--next-date", default="", help="验证日(T，云端消费当日) YYYY-MM-DD，默认今日")
    p.add_argument("--source", default="", help="预期 position_expectation JSONL（默认自动兜底）")
    p.add_argument("--out-dir", default="", help="待上传 CSV 根目录（默认 PTRADE_BRIDGE_DIR）")
    p.add_argument("--require-provider", action="store_true", help="提供方缺失输入 -> 中止(rc=2)")
    p.add_argument("--skip-lianban", action="store_true", help="跳过涨停名单导出(步骤2)")
    a = p.parse_args(argv)

    td, nt = _resolve_defaults(a.date, a.next_date)
    out = a.out_dir or bridge.PTRADE_BRIDGE_DIR
    print("[premarket] 复盘日(T-1)=%s 验证日(T)=%s out=%s" % (td, nt, out))
    rc = 0

    # 步骤0：提供方就绪探活
    print("[premarket] 步骤0 提供方(AXquant)就绪校验 复盘日=%s 预期日=%s" % (td, nt))
    axc.probe_report(td, nt)
    _miss = axc.missing(td, nt)
    if _miss:
        print("[premarket] 提供方缺失输入: %s" % ", ".join(_miss))
        if a.require_provider:
            print("[premarket] --require-provider 已置 -> 中止")
            return 2
        print("[premarket] 警告：缺失输入将导致名单为空/预期缺失（--require-provider 可强制中止）")

    # 步骤1：生成今日预期 CSV（from-jsonl -> validate -> 验证日命名 + latest）
    print("[premarket] 步骤1 构建+校验预期桥接 CSV ->")
    _rc = rb.run_build(nt, a.source, out)
    _src_csv = os.path.join(out, "expectation_%s.csv" % nt)   # 验证日命名（云端消费当日）
    _gen_csv = os.path.join(out, "expectation_%s.csv" % td)   # 生成日命名兜底
    _latest_csv = os.path.join(out, "expectation_latest.csv") # 稳定指针（云端优先读）
    _nrows = _rows_of(_src_csv)
    _src = a.source or axc.paths(td, nt)["expectation_source"]
    if _rc == 0 and _nrows > 0:
        _copy_alias(_src_csv, _gen_csv, _latest_csv)
    elif _source_is_empty_marker(_src):
        # 空仓 marker：今日无持仓预期属正常，不上传、不覆盖既有文件
        print("[premarket] 预期源为「空仓 marker」-> 今日无持仓预期，不上传预期文件（正常，不覆盖 %s）" % os.path.basename(_gen_csv))
    else:
        rc = _rc or 3
        print("[premarket] 预期构建未通过(rc=%d)：请先跑 run_one_click_after_close.py --date %s 生成预期 JSONL（未覆盖既有文件）" % (_rc, td))
    if _nrows <= 0 and os.path.isfile(_src_csv):
        # 清理无数据行的空 CSV（防被「定时上传=按文件夹」误带上云，云端读到 0 行会 expect_buy=0）
        try:
            os.remove(_src_csv)
            print("[premarket] 清理无数据行的 %s（避免被自动上传带上云）" % os.path.basename(_src_csv))
        except OSError:
            pass

    # 步骤2：T-1 涨停/连板名单
    if not a.skip_lianban:
        print("[premarket] 步骤2 导出涨停/连板名单(T-1=%s) ->" % td)
        try:
            import export_lianban
            export_lianban.run(td, None, out, alias="")
        except Exception as e:
            print("[premarket] export_lianban 失败(不影响预期): %r" % e)
        # 步骤2b: 情绪冰点/回暖基线（T-1 数据，docs/40）
        try:
            import export_sentiment
            export_sentiment.run(td, out)
        except Exception as e:
            print("[premarket] export_sentiment 失败(不影响预期/名单): %r" % e)

    # 步骤3：产出一致性核对
    print("[premarket] 步骤3 产出一致性核对 ...")
    _exp_csv = os.path.join(out, "expectation_latest.csv")
    if os.path.isfile(_exp_csv):
        _fe = axc.check_expectation_consistency(_exp_csv, _src)
        print("  [预期] CSV=%s src=%s ok=%s %s" % (_fe["csv_codes"], _fe["src_codes"], _fe["ok"], _fe["note"]))
        if not _fe["ok"]:
            rc = rc or 3
    else:
        print("  [预期] 无 expectation_latest.csv（空仓/无预期或未生成均属正常，见步骤1）")
    _zt_csv = os.path.join(out, "zt_lianban_latest.csv")
    if os.path.isfile(_zt_csv):
        _fz = axc.check_zt_consistency(_zt_csv, td)
        print("  [名单] zt=%s boards=%s date=%s ok=%s %s" % (_fz["zt_rows"], _fz["board_rows"], _fz["zt_date"], _fz["ok"], _fz["note"]))
        if not _fz["ok"]:
            rc = rc or 4
    else:
        print("  [名单] 未找到 %s —— 跑 run_one_click_after_close / AXquant 产出涨停池后重试" % _zt_csv)

    # 步骤4：上传勾选清单
    print("[premarket] 步骤4 上传勾选清单（T 日 09:20 前完成上传）")
    files = [
        ("预期 CSV(验证日命名)", os.path.join(out, "expectation_%s.csv" % nt)),
        ("预期 CSV(生成日命名)", _gen_csv),
        ("预期 CSV(latest 稳定指针)", _latest_csv),
        ("涨停/连板名单(latest)", _zt_csv),
        ("自选股(可选)", os.path.join(out, "selfwatch.csv")),
    ]
    for label, fp in files:
        rows = _rows_of(fp)
        state = ("%d 行" % rows) if rows >= 0 else "缺失"
        print("  待上传  %-22s %s" % (label, fp))
        print("          -> 状态: %s" % state)
    print("  云端落点(定时上传绑定 %s 后, 策略 _research_roots 自动依次查找):" % out)
    print("          /home/fly/notebook/(upload_file/)(data/)(data/upload_file/) 下同名文件")
    print("  盘中核对关键字:")
    print("          [pool] expect_buy=N>0 | expectation file loaded | [exp] 涨停池竞价三态合成 -> exceed=N")
    print("          [zt-lianban] loaded -> N | [seal]/[firstzt]/[l2] 正常")
    print("  结论: %s" % ("待上传文件已就绪" if rc == 0 else "存在缺项(rc=%d)，按上方提示补齐" % rc))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
