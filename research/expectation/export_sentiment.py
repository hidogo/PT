#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""导出「情绪冰点/回暖基线」CSV（docs/40 契约，与 zt_lianban 同链）。

数据源：AXquant limit_up_boards_<date>.json 的 summary（涨停/炸板/红盘率/连板），
规则（用户确认）：
  - T 日冰点判定：红盘率(advance_rate) < 冰点阈值 或 封板率 < 阈值 或 涨停家数 < 下限 -> ice=1；
  - 连续冰点天数 ice_streak：读上一版 sentiment_latest.csv 累计；冰点则 +1，否则归 0；
    （v0.35 日期守卫：latest 的 date == 当前日期 → 同日重复运行，不重复累计；latest 更晚 → 视为无前置）
  - T+1 恢复（红盘比恢复）判「情绪回暖」由云端 `_sentiment_warm` 消费，冰点越久恢复阈值越低；
  - 闭环（v0.30）：非冰点日为回暖/延续日，连续天数 warm_days 累计；warm_days >= 分歧阈值(默认3) -> divergence=1（分歧概率上升）；
    phase: ice=冰点 / warm=回暖首日 / cont=回暖延续。
列：date,limit_up,break_count,seal_rate,advance_rate,max_board,lianban_count,ice,ice_streak,warm_days,phase,divergence,emotion,emotion_basis
  seal_rate 存小数(0-1)；advance_rate 存百分比数值(如 37.46)；ice/divergence 0/1；
  emotion 为复盘 marker 机器判定的情绪温度档位（冰点/偏冷/回暖/发酵/高潮/过热），emotion_basis 为档位依据，
  均来自 position_review marker extra.emotion_temperature；缺失写空串（区别于真实值）。

输出（待上传文件夹，客户端定时上传=按文件夹）：
  sentiment_<date>.csv    当日情绪基线
  sentiment_latest.csv    稳定指针（云端盘前首选读）
列（与 SENTIMENT_HEADER 一致，两文件同构）：
  date,limit_up,break_count,seal_rate,advance_rate,max_board,lianban_count,ice,ice_streak,warm_days,phase,divergence,emotion,emotion_basis
  seal_rate 存小数(0-1)；advance_rate 存百分比数值(如 37.46)；ice/divergence 0/1；
  emotion/emotion_basis 来自复盘 marker 情绪温度（见上），缺失为空串。

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
    "emotion", "emotion_basis",
]


def _fnum(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _default_axquant_review_dir() -> str:
    # D:/PROJ/PT/research/expectation -> D:/PROJ/AXquant/data/review
    return os.path.abspath(os.path.join(_HERE, "..", "..", "..", "AXquant", "data", "review"))


def _prune_old(out_dir: str, keep_days: int = 3) -> int:
    """待上传根只保留最近 keep_days 个 sentiment_<date>.csv；更早移入 archive/（保留审计，不上传）。

    与 zt_lianban 的 keep_days=3 对齐：定时上传=按文件夹，根目录瘦身防历史被带上云；
    archive/ 为审计目录（本意不上传），移入而非删除，历史序列可回溯。
    只匹配 sentiment_YYYY-MM-DD.csv 命名且路径在 out_dir 内，杜绝误删/误移。
    """
    import re as _re
    pat = _re.compile(r"^sentiment_(\d{4}-\d{2}-\d{2})\.csv$")
    dated = []
    for name in os.listdir(out_dir):
        m = pat.match(name)
        if not m:
            continue
        full = os.path.join(out_dir, name)
        if not os.path.isfile(full):
            continue
        dated.append((m.group(1), full))
    dated.sort()
    moved = 0
    arc = os.path.join(out_dir, "archive")
    for _, full in dated[:-max(1, int(keep_days))]:
        try:
            os.makedirs(arc, exist_ok=True)
            os.replace(full, os.path.join(arc, os.path.basename(full)))
            moved += 1
        except OSError:
            pass
    if moved:
        print("[sentiment] 历史日期文件移入 archive/ %d 个（根目录仅留最近 %d 个）" % (moved, keep_days))
    return moved


def _read_red_ratio(date: str, pr_dir: str | None = None) -> float | None:
    """读 AXquant position_review_<date>.jsonl 的 marker extra.emotion_temperature.red_ratio_pct
    （全市场红盘比%，tdx ZAF 收盘实时值）；缺失 -> None（调用方回退）。"""
    fp = os.path.join(pr_dir or _default_axquant_review_dir(), "position_review_%s.jsonl" % date)
    if not os.path.isfile(fp):
        return None
    try:
        with open(fp, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                if rec.get("record_type") != "position_review_marker":
                    continue
                et = (rec.get("extra") or {}).get("emotion_temperature") or {}
                if et.get("red_ratio_pct") is not None:
                    return float(et["red_ratio_pct"])
    except Exception:
        return None
    return None


def _read_emotion(date: str, pr_dir: str | None = None) -> dict:
    """读 AXquant position_review_<date>.jsonl 的 marker extra.emotion_temperature
    （复盘任务机器判定的情绪温度档位+依据）；文件/字段缺失 -> 空串。"""
    fp = os.path.join(pr_dir or _default_axquant_review_dir(), "position_review_%s.jsonl" % date)
    if not os.path.isfile(fp):
        return {"conclusion": "", "basis": ""}
    try:
        with open(fp, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                if rec.get("record_type") != "position_review_marker":
                    continue
                et = (rec.get("extra") or {}).get("emotion_temperature") or {}
                return {
                    "conclusion": str(et.get("conclusion") or "").strip(),
                    "basis": str(et.get("basis") or "").strip(),
                }
    except Exception:
        return {"conclusion": "", "basis": ""}
    return {"conclusion": "", "basis": ""}


def _read_prev_latest(out_dir: str):
    """读上一版 sentiment_latest.csv -> (ice, ice_streak, warm_days, prev_date)；无/坏 -> (False, 0, 0, None)。"""
    fp = os.path.join(out_dir, "sentiment_latest.csv")
    if not os.path.isfile(fp):
        return False, 0, 0, None
    try:
        with open(fp, "r", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        if len(rows) < 2:
            return False, 0, 0, None
        hdr = [x.strip().lower() for x in rows[0]]
        rec = dict(zip(hdr, rows[1][:len(hdr)]))
        return (bool(int(_fnum(rec.get("ice")))), int(_fnum(rec.get("ice_streak"))),
                int(_fnum(rec.get("warm_days"))), str(rec.get("date") or ""))
    except Exception:
        return False, 0, 0, None


def run(date: str | None = None, out_dir: str | None = None, lub_dir: str | None = None,
        pr_dir: str | None = None,
        ice_advance: float = DEFAULT_ICE_ADVANCE, ice_seal: float = DEFAULT_ICE_SEAL,
        ice_limit_up: int = DEFAULT_ICE_LIMIT_UP, divergence_start: int = DEFAULT_DIVERGENCE_START,
        keep_days: int = 3) -> str:
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
    red_ratio = _read_red_ratio(date, pr_dir)                  # 全市场红盘比%（tdx ZAF 收盘实时值，优先）
    advance_rate = red_ratio if red_ratio is not None else _fnum(summary.get("advance_rate_pct"))
    emotion = _read_emotion(date, pr_dir)                      # 情绪温度档位+依据（复盘 marker）
    if red_ratio is not None:
        print("[sentiment] 红盘比来源: %s position_review emotion_temperature red_ratio_pct=%.2f%%（全市场，优先）" % (date, red_ratio))
    else:
        print("[sentiment] WARN: 无 %s 的 position_review red_ratio —— 回退 summary.advance_rate_pct=%.2f%%（天梯有限样本，非全市场红盘比）" % (date, advance_rate))
    lianban_count = int(_fnum(summary.get("lianban_count")))
    max_board = int(_fnum(summary.get("max_board")))
    ice = bool((advance_rate < ice_advance) or (seal_rate * 100.0 < ice_seal) or (pool_total < ice_limit_up))
    prev_ice, prev_streak, prev_warm_days, prev_date = _read_prev_latest(out_dir)
    if prev_date and prev_date > date:
        # v0.35 日期守卫：latest 已指向更晚日期（回补历史/异常顺序）→ 不作为前置，避免未来状态污染
        print("[sentiment] WARN: latest date=%s > 当前 %s —— 视为无前置，不累计" % (prev_date, date))
        prev_ice, prev_streak, prev_warm_days, prev_date = False, 0, 0, None
    same_day = bool(prev_date) and prev_date == date
    if same_day:
        # v0.35 日期守卫：latest 已含当日状态（同日重复运行）-> 不重复累计，沿用累计值
        if ice:
            ice_streak, warm_days, phase = prev_streak, 0, "ice"
        elif prev_ice:
            ice_streak, warm_days, phase = 0, 1, "warm"
        else:
            ice_streak, warm_days, phase = 0, prev_warm_days, "cont"
        print("[sentiment] 同日守卫: prev_date=%s == 当前 %s -> 不重复累计 streak=%d warm_days=%d"
              % (prev_date, date, ice_streak, warm_days))
    else:
        ice_streak = (prev_streak + 1) if ice else 0
        if ice:
            warm_days, phase = 0, "ice"
        elif prev_ice:
            warm_days, phase = 1, "warm"
        else:
            warm_days, phase = prev_warm_days + 1, "cont"
    divergence = 1 if warm_days >= divergence_start else 0

    os.makedirs(out_dir, exist_ok=True)
    row = [date, pool_total, break_total, "%.4f" % seal_rate, "%.2f" % advance_rate,
           max_board, lianban_count, int(ice), ice_streak, warm_days, phase, divergence,
           emotion.get("conclusion", ""), emotion.get("basis", "")]
    csv_path = os.path.join(out_dir, "sentiment_%s.csv" % date)
    latest = os.path.join(out_dir, "sentiment_latest.csv")
    for fp in (csv_path, latest):
        tmp = fp + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(SENTIMENT_HEADER)
            w.writerow(row)
        os.replace(tmp, fp)
    print("[sentiment] %s -> ice=%d streak=%d warm_days=%d phase=%s divergence=%d adv=%.1f%% seal=%.0f%% limup=%d brk=%d emotion=%s -> %s"
          % (date, int(ice), ice_streak, warm_days, phase, divergence, advance_rate, seal_rate * 100.0,
             pool_total, break_total, emotion.get("conclusion") or "-", csv_path))
    print("[sentiment] 规则: T日冰点(ice=1) -> T+1 红盘比恢复=回暖(云端 _sentiment_warm 消费)；"
          "T+1 继续冰点 -> streak+1，下交易日再验证回暖且恢复阈值降低；回暖/延续 warm_days>=%d -> 分歧概率上升" % divergence_start)
    _prune_old(out_dir, keep_days)
    return csv_path


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="export_sentiment", description="导出情绪冰点/回暖基线 CSV")
    p.add_argument("--date", default="", help="涨停池数据日(收盘日 T) YYYY-MM-DD")
    p.add_argument("--lub", default="", help="AXquant 涨停池 json 目录(默认自动定位 D:/PROJ/AXquant/docs/review)")
    p.add_argument("--pr-dir", default="", help="AXquant position_review 目录(默认自动定位 D:/PROJ/AXquant/data/review)")
    p.add_argument("--out-dir", default="", help="待上传文件夹(默认 PTRADE_BRIDGE_DIR)")
    p.add_argument("--ice-advance", type=float, default=DEFAULT_ICE_ADVANCE)
    p.add_argument("--ice-seal", type=float, default=DEFAULT_ICE_SEAL)
    p.add_argument("--ice-limit-up", type=int, default=DEFAULT_ICE_LIMIT_UP)
    p.add_argument("--divergence-start", type=int, default=DEFAULT_DIVERGENCE_START)
    p.add_argument("--keep-days", type=int, default=3, help="根目录保留 sentiment_<date>.csv 天数（更早移入 archive/）")
    a = p.parse_args(argv)
    run(a.date, a.out_dir, a.lub, a.pr_dir, a.ice_advance, a.ice_seal, a.ice_limit_up, a.divergence_start, a.keep_days)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
