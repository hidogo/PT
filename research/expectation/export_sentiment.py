#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""导出「情绪冰点/回暖基线」CSV（docs/40 契约，与 zt_lianban 同链）。

数据源：AXquant limit_up_boards_<date>.json 的 summary（涨停/炸板/红盘率/连板），
规则（用户确认）：
  - T 日冰点判定：红盘率(advance_rate) < 冰点阈值 或 封板率 < 阈值 或 涨停家数 < 下限 -> ice=1；
  - 连续冰点天数 ice_streak：读上一版 sentiment_latest.csv 累计；冰点则 +1，否则归 0；
  - T+1 恢复（红盘比恢复）判「情绪回暖」由云端 `_sentiment_warm` 消费，冰点越久恢复阈值越低；
  - 闭环（v0.30）：非冰点日为回暖/延续日，连续天数 warm_days 累计；warm_days >= 分歧阈值(默认3) -> divergence=1（分歧概率上升）；
    phase: ice=冰点 / warm=回暖首日 / cont=回暖延续。
列：date,limit_up,break_count,seal_rate,advance_rate,max_board,lianban_count,ice,ice_streak,warm_days,phase,divergence
  seal_rate 存小数(0-1)；advance_rate 存百分比数值(如 37.46)；ice/divergence 0/1。

输出（待上传文件夹，客户端定时上传=按文件夹）：
  sentiment_<date>.csv    当日情绪基线
  sentiment_latest.csv    稳定指针（云端盘前首选读）
列：date,limit_up,break_count,seal_rate,advance_rate,max_board,lianban_count,ice,ice_streak
  seal_rate 存小数(0-1)；advance_rate 存百分比数值(如 37.46)；ice 0/1。

用法（本机 Python3.10，无需登录）：
  python export_sentiment.py [--date 2026-10-19] [--lub <axquant json 目录>] [--out-dir <上传文件夹>]
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import bridge  # noqa: E402
import export_lianban  # noqa: E402  # 复用 default_lub_path / _code_ptrade


DEFAULT_ICE_ADVANCE = 40.0   # 红盘率%(advance_rate) < 此值 = 冰点
DEFAULT_ICE_SEAL = 45.0      # 封板率%(seal_rate) < 此值 = 冰点
DEFAULT_ICE_LIMIT_UP = 30    # 涨停家数 < 此值 = 冰点
DEFAULT_DIVERGENCE_START = 3  # 连续回暖/延续 >= 此天数 -> divergence=1（分歧概率上升）

SENTIMENT_HEADER = [
    "date", "limit_up", "break_count", "seal_rate", "advance_rate",
    "max_board", "lianban_count", "ice", "ice_streak", "warm_days", "phase", "divergence",
]


def _fnum(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _read_prev_latest(out_dir: str):
    """读上一版 sentiment_latest.csv -> (ice, ice_streak, warm_days)；无/坏 -> (False, 0, 0)。"""
    fp = os.path.join(out_dir, "sentiment_latest.csv")
    if not os.path.isfile(fp):
        return False, 0, 0
    try:
        with open(fp, "r", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        if len(rows) < 2:
            return False, 0, 0
        hdr = [x.strip().lower() for x in rows[0]]
        rec = dict(zip(hdr, rows[1][:len(hdr)]))
        return (bool(int(_fnum(rec.get("ice")))), int(_fnum(rec.get("ice_streak"))),
                int(_fnum(rec.get("warm_days"))))
    except Exception:
        return False, 0, 0


def run(date: str | None = None, out_dir: str | None = None, lub_dir: str | None = None,
        ice_advance: float = DEFAULT_ICE_ADVANCE, ice_seal: float = DEFAULT_ICE_SEAL,
        ice_limit_up: int = DEFAULT_ICE_LIMIT_UP, divergence_start: int = DEFAULT_DIVERGENCE_START) -> str:
    """导出情绪基线 CSV；未找到涨停池 json 返回空串。"""
    date = date or datetime.date.today().isoformat()
    out_dir = out_dir or bridge.PTRADE_BRIDGE_DIR
    lub = export_lianban.default_lub_path(date, lub_dir)
    if not os.path.exists(lub):
        print("[sentiment] 未找到涨停池 %s —— 跳过(等 AXquant 产出)" % lub)
        return ""
    with open(lub, "r", encoding="utf-8") as f:
        payload = json.load(f)
    pool = (payload or {}).get("pool") or {}
    summary = (payload or {}).get("summary") or {}
    pool_total = int(_fnum(summary.get("pool_total"), 0) or 0)
    if not pool_total:
        pool_total = len(pool.get("item") or [])
    break_total = int(_fnum(summary.get("break_total"), 0) or 0)
    seal_rate = (pool_total / (pool_total + break_total)) if (pool_total + break_total) > 0 else 1.0
    advance_rate = _fnum(summary.get("advance_rate_pct"))      # 红盘率%（有限样本估算）
    lianban_count = int(_fnum(summary.get("lianban_count")))
    max_board = int(_fnum(summary.get("max_board")))
    ice = bool((advance_rate < ice_advance) or (seal_rate * 100.0 < ice_seal) or (pool_total < ice_limit_up))
    prev_ice, prev_streak, prev_warm_days = _read_prev_latest(out_dir)
    ice_streak = (prev_streak + 1) if ice else 0
    # v0.30 闭环：非冰点日为回暖/延续日；warm_days 连续累计；warm_days>=分歧阈值 -> divergence=1
    if ice:
        phase, warm_days, divergence = "ice", 0, 0
    elif prev_ice:
        phase, warm_days = "warm", 1
        divergence = 1 if warm_days >= divergence_start else 0
    else:
        phase, warm_days = "cont", prev_warm_days + 1
        divergence = 1 if warm_days >= divergence_start else 0

    os.makedirs(out_dir, exist_ok=True)
    row = [date, pool_total, break_total, "%.4f" % seal_rate, "%.2f" % advance_rate,
           max_board, lianban_count, int(ice), ice_streak, warm_days, phase, divergence]
    csv_path = os.path.join(out_dir, "sentiment_%s.csv" % date)
    latest = os.path.join(out_dir, "sentiment_latest.csv")
    for fp in (csv_path, latest):
        tmp = fp + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(SENTIMENT_HEADER)
            w.writerow(row)
        os.replace(tmp, fp)
    print("[sentiment] %s -> ice=%d streak=%d warm_days=%d phase=%s divergence=%d adv=%.1f%% seal=%.0f%% limup=%d brk=%d -> %s"
          % (date, int(ice), ice_streak, warm_days, phase, divergence, advance_rate, seal_rate * 100.0,
             pool_total, break_total, csv_path))
    print("[sentiment] 规则: T日冰点(ice=1) -> T+1 红盘比恢复=回暖(云端 _sentiment_warm 消费)；"
          "T+1 继续冰点 -> streak+1，下交易日再验证回暖且恢复阈值降低；回暖/延续 warm_days>=%d -> 分歧概率上升" % divergence_start)
    return csv_path


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="export_sentiment", description="导出情绪冰点/回暖基线 CSV")
    p.add_argument("--date", default="", help="涨停池数据日(收盘日 T) YYYY-MM-DD")
    p.add_argument("--lub", default="", help="AXquant 涨停池 json 目录(默认自动定位 D:/PROJ/AXquant/docs/review)")
    p.add_argument("--out-dir", default="", help="待上传文件夹(默认 PTRADE_BRIDGE_DIR)")
    p.add_argument("--ice-advance", type=float, default=DEFAULT_ICE_ADVANCE)
    p.add_argument("--ice-seal", type=float, default=DEFAULT_ICE_SEAL)
    p.add_argument("--ice-limit-up", type=int, default=DEFAULT_ICE_LIMIT_UP)
    p.add_argument("--divergence-start", type=int, default=DEFAULT_DIVERGENCE_START)
    a = p.parse_args(argv)
    run(a.date, a.out_dir, a.lub, a.ice_advance, a.ice_seal, a.ice_limit_up, a.divergence_start)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
