#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""盘前一键：生成今日待上传文件 + 校验 + 上传勾选清单（无需登录，不重跑收盘复盘）。

T-1 收盘已跑过 run_one_click_after_close 生成 position_expectation_<T>.jsonl 的前提下，
T 日 09:00 验证/补跑、 09:15 前完成上传：（收盘一键为交易日 16:30 兜底，复盘任务链完成后也会触发）
步骤2c “盘前供给核对”：预期(日期=T)、名单(日期=T-1)、情绪(日期=T-1，红盘比优先 position_review 全市场)逐项确认；
若 16:30 时 AXquant 复盘未完成（情绪 WARN 回退天梯样本），09:00 补跑自动修正。
  步骤0  提供方(AXquant)就绪探活            axc.probe_report / missing
  步骤1  生成预期 CSV                        expectation_<T>.csv + latest（复用 run_expectation_build）
  步骤2  生成涨停/连板名单                    zt_lianban_latest.csv（T-1 数据，复用 export_lianban）
  步骤2e 概念板块映射周更检查              周一固定刷新 boards_latest.csv（低频，UNCHANGED 跳过）
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

SCRIPT_VERSION = "v0.72c"   # 板块周更（周一固定）：步骤2e 概念板块映射每周一检查刷新（低频，内容未变跳过覆盖）


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


def _sha1_of(path: str) -> str:
    import hashlib
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _first_row(path: str) -> dict:
    import csv as _csv
    try:
        with open(path, "r", encoding="utf-8") as f:
            rows = list(_csv.reader(f))
    except Exception:
        return {}
    if len(rows) < 2:
        return {}
    hdr = [x.strip().lower() for x in rows[0]]
    return dict(zip(hdr, rows[1][:len(hdr)]))


def _check_upload_file(label: str, path: str, expect_date: str) -> tuple:
    """上传前硬校验(单文件)：存在 + 行数>0 + date 列 == expect_date。返回 (失败计数 0/1, 说明)。"""
    if not os.path.isfile(path):
        return (1, "%-22s 缺失 -> FAIL" % label)
    rows = _rows_of(path)
    if rows <= 0:
        return (1, "%-22s rows=%d -> FAIL(空表不可上传)" % (label, rows))
    dt = str((_first_row(path) or {}).get("date") or "")
    if expect_date and dt != expect_date:
        return (1, "%-22s rows=%d date=%s -> FAIL(期望 %s)" % (label, rows, dt or "(无)", expect_date))
    return (0, "%-22s rows=%d date=%s -> OK" % (label, rows, dt or "-"))


def _check_expectation_meta(latest_csv: str, meta_fp: str) -> tuple:
    """预期 CSV 与 archive meta 的 row_count/sha1 硬校验（防上传前被旧文件覆盖）。返回 (失败计数 0/1, 说明)。"""
    rows = _rows_of(latest_csv)
    if not os.path.isfile(latest_csv) or rows <= 0:
        return (1, "预期 CSV(latest) rows=%d -> FAIL(缺失/空表)" % rows)
    if not os.path.isfile(meta_fp):
        return (0, "预期 CSV(latest) rows=%d -> OK(无 meta，仅行数校验)" % rows)
    try:
        with open(meta_fp, "r", encoding="utf-8") as f:
            meta = json.load(f)
    except Exception as e:
        return (1, "预期 CSV(latest) meta 读取失败 %r -> FAIL" % e)
    mrow = meta.get("row_count")
    msha = str(meta.get("sha1") or "")
    sha = _sha1_of(latest_csv)
    if mrow is not None and int(mrow) != rows:
        return (1, "预期 CSV(latest) rows=%d meta_rows=%s -> FAIL(行数不一致，疑似被覆盖)" % (rows, mrow))
    if msha and msha != sha:
        return (1, "预期 CSV(latest) sha1=%s meta_sha1=%s -> FAIL(内容与 meta 不一致)" % (sha[:12], msha[:12]))
    return (0, "预期 CSV(latest) rows=%d sha1=%s -> OK(与 meta 一致)" % (rows, sha[:12]))

def _archived_note(fp: str, out_root: str) -> str:
    """目录瘦身会把 dated 文件移入 archive/（只上传 _latest）：返回归档说明，供清单避免误判缺失。"""
    _arc = os.path.join(out_root, "archive", os.path.basename(fp))
    if os.path.isfile(_arc) and _rows_of(_arc) > 0:
        return "已归档(仅上传 _latest) archive/%s" % os.path.basename(_arc)
    return ""


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
    p.add_argument("--skip-selfwatch", action="store_true", help="跳过自选股同步（默认每个交易日盘前自动从客户端刷新）")
    a = p.parse_args(argv)

    td, nt = _resolve_defaults(a.date, a.next_date)
    out = a.out_dir or bridge.PTRADE_BRIDGE_DIR
    print("[premarket] 复盘日(T-1)=%s 验证日(T)=%s out=%s" % (td, nt, out))
    print("[premarket] %s" % SCRIPT_VERSION)
    rc = 0

    # 步骤0：提供方就绪探活
    print("[premarket] 步骤0 提供方(AXquant)就绪校验 复盘日=%s 预期日=%s" % (td, nt))
    axc.probe_report(td, nt)
    _mw = axc.marker_warns(td, nt)
    if _mw:
        print("[WARN] 预期链路断链（空 marker）: %s —— 预期 CSV 将缺失/为空，云端 expect_buy=0。请检查本地持仓桥接(QMT position_data.json)与 AXquant 复盘任务是否真正产出。" % "; ".join(_mw))
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
    _local_exp = bridge.expectation_store.default_expectation_path(nt)
    _src = a.source or (_local_exp if os.path.isfile(_local_exp) else axc.paths(td, nt)["expectation_source"])
    _exp_expected = True
    if _rc == 0 and _nrows > 0:
        _copy_alias(_src_csv, _gen_csv, _latest_csv)
    elif _source_is_empty_marker(_src):
        _exp_expected = False
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

    # 步骤2c：盘前供给核对（9:00 验证/补跑）：预期/名单/情绪/自选 就绪性 + 日期 + 口径
    print("[premarket] 步骤2c 盘前供给核对（9:00 验证/补跑） ...")
    import csv as _csv75
    def _head_row(fp):
        try:
            with open(fp, "r", encoding="utf-8") as _f:
                rows = list(_csv75.reader(_f))
            if len(rows) < 2:
                return None
            hdr = [x.strip().lower() for x in rows[0]]
            return dict(zip(hdr, rows[1][:len(hdr)]))
        except Exception:
            return None
    def _supply(label, fp, expect_date):
        rec = _head_row(fp)
        if rec is None:
            print("  [供给] %-20s 缺失 -> 需补跑/上传" % label)
            return 1
        dt = str(rec.get("date") or "")
        rows = _rows_of(fp)
        ok = (rows > 0) and (not expect_date or dt == expect_date)
        print("  [供给] %-20s date=%s rows=%d -> %s" % (label, dt or "(无date列)", rows, "OK" if ok else "日期不符/空行"))
        return 0 if ok else 1
    _miss2 = 0
    _exp_latest = os.path.join(out, "expectation_latest.csv")
    _exp_nt = os.path.join(out, "expectation_%s.csv" % nt)
    _exp_ok = (os.path.isfile(_exp_latest) and _rows_of(_exp_latest) > 0 and
               os.path.isfile(_exp_nt) and _rows_of(_exp_nt) > 0)
    print("  [供给] %-20s date=%s rows=%d -> %s" % ("预期 CSV(latest)", nt, _rows_of(_exp_latest), "OK" if _exp_ok else "缺失/空行"))
    _miss2 += 0 if _exp_ok else 1
    _miss2 += _supply("涨停名单(latest)", os.path.join(out, "zt_lianban_latest.csv"), td)
    _miss2 += _supply("情绪基线(latest)", os.path.join(out, "sentiment_latest.csv"), td)
    _sent = _head_row(os.path.join(out, "sentiment_latest.csv"))
    if _sent:
        _adv = _sent.get("advance_rate") or ""
        _sadv = None
        try:
            import export_lianban as _el75
            _lub = _el75.default_lub_path(td)
            if os.path.isfile(_lub):
                _sadv = json.load(open(_lub, encoding="utf-8")).get("summary", {}).get("advance_rate_pct")
        except Exception:
            pass
        try:
            _advf, _sadvf = float(_adv), float(_sadv)
        except Exception:
            _advf = _sadvf = None
        if _sadvf is not None and _advf is not None and abs(_advf - _sadvf) < 0.01:
            print("  [供给] 情绪红盘比=%.2f%% 与涨停池天梯样本一致 -> 口径=天梯回退（建议收盘一键在 AXquant 复盘完成后重跑）" % _advf)
        elif _advf is not None:
            print("  [供给] 情绪红盘比=%.2f%% 与天梯样本不同 -> 口径=position_review 全市场（优先，正确）" % _advf)
    _self = os.path.join(out, "selfwatch.csv")
    if os.path.isfile(_self):
        print("  [供给] %-20s rows=%d -> OK（可选）" % ("自选股", _rows_of(_self)))
    else:
        print("  [供给] %-20s 缺失（可选，有自选需求再上传）" % "自选股")
    if _miss2:
        rc = rc or 5
        print("  [供给] 存在缺项/date 不符 (rc=%d) -> 按上方提示补跑（收盘一键 / AXquant 复盘后重跑）" % rc)
    else:
        print("  [供给] 盘前供给全部就绪 -> 等 09:15 前定时上传")

    # 步骤2d: 自选股同步（默认执行；客户端未登录/无 XML 时保留既有文件并提示）
    if not a.skip_selfwatch:
        try:
            import sync_selfwatch as ss
            ss.sync()
        except Exception as e:
            print("[premarket] sync_selfwatch 失败(不影响预期/名单): %r" % e)

    # 步骤2e: 概念板块映射周更（周一固定，低频；复用 export_boards，内容未变 UNCHANGED 跳过）
    print("[premarket] 步骤2e 概念板块映射周更检查（周一固定） ...")
    try:
        import export_boards as _ebo
        _boards_fp = os.path.join(out, "boards_latest.csv")
        _due, _age = _ebo.boards_refresh_due(datetime.date.today(), _boards_fp)
        if _due:
            _age_txt = ("%.1f 天" % _age) if _age is not None else "缺失"
            print("  [boards] 周一/到期 -> 刷新板块映射（上一版 age=%s）" % _age_txt)
            _br = _ebo.run(out_dir=out)   # 默认 concept + rank-limit 5
            print("  [boards] %s rows=%d boards=%d" % (_br["status"], _br["rows"], _br["boards"]))
        else:
            print("  [boards] 非周一 -> 跳过（保持低频，上一版 age=%.1f 天）" % (_age or 0.0))
    except Exception as e:
        print("[premarket] 板块周更检查失败(不影响预期/名单): %r" % e)

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

    # 步骤3b：待上传目录瘦身/归档（定时上传有数据限制：上传前把日期文件只留最新 N 个，更早移入 archive/ 不上传）
    try:
        import maintain_bridge_dir as _mbd
        _margv = ["--root", out] if a.out_dir else []
        _mbd.main(_margv)
    except Exception as _e:
        print("[premarket] maintain_bridge_dir 失败(不影响预期/上传): %r" % _e)

    # 步骤3c：上传前硬校验（v0.72）—— 行数>0 + date 对齐 + 预期 CSV 与 archive meta 的 row_count/sha1 一致
    print("[premarket] 步骤3c 上传前硬校验（行数 / date / sha1 vs meta）...")
    _hard = 0
    for _lbl, _fp, _exp in (
        ("涨停/连板(latest)", _zt_csv, td),
        ("情绪基线(latest)", os.path.join(out, "sentiment_latest.csv"), td),
    ):
        _bad, _msg = _check_upload_file(_lbl, _fp, _exp)
        print("  [硬校验] " + _msg)
        _hard += _bad
    _meta_fp = os.path.join(out, "archive", "expectation_%s.csv.meta.json" % nt)
    if _exp_expected:
        _bad, _msg = _check_expectation_meta(_latest_csv, _meta_fp)
        print("  [硬校验] " + _msg)
        _hard += _bad
    else:
        print("  [硬校验] 预期 CSV(latest) 空仓 marker -> SKIP(正常无预期，不上传)")
    if _hard:
        rc = rc or 6
        print("  [硬校验] %d 项未通过 -> 禁止上传，先补齐/重跑（rc=%d）" % (_hard, rc))
    else:
        print("  [硬校验] 全部通过 -> 可在 09:15 前勾选上传")

    # 步骤4：上传勾选清单
    print("[premarket] 步骤4 上传勾选清单（T 日 09:15 前完成上传；硬校验未通过不可上传）")
    files = [
        ("预期 CSV(验证日命名)", os.path.join(out, "expectation_%s.csv" % nt)),
        ("预期 CSV(生成日命名)", _gen_csv),
        ("预期 CSV(latest 稳定指针)", _latest_csv),
        ("涨停/连板名单(latest)", _zt_csv),
        ("情绪基线(latest)", os.path.join(out, "sentiment_latest.csv")),
        ("自选股(可选)", os.path.join(out, "selfwatch.csv")),
    ]
    for label, fp in files:
        rows = _rows_of(fp)
        if rows >= 0:
            state = "%d 行" % rows
        else:
            state = _archived_note(fp, out) or "缺失"
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
