# -*- coding: utf-8 -*-
"""自包含 A 股交易日历（复刻，独立运行、零 axquant 依赖）。

数据源优先级：
  1. 权威交易日缓存 data/tmp/calendar.json（由研究环境 get_trade_days 导出，格式见
     calendar_export_research.py）；命中即精确含节假日/调休。
  2. 缓存缺失/目标日期晚于缓存 -> 周末规则近似（不精确节假日，避免误伤未来交易日）。

提供：is_trading_day / previous_trading_day / next_trading_day / cache 读写。
供 closeout_review、build_expectation_bridge 的“上一/下一交易日”换算使用。
"""
from __future__ import annotations

import datetime as _dt
import json
import os

# .../expectation/bridge -> 上溯4级到 PT（与 expectation_store 数据根一致）
_path_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def data_dir() -> str:
    override = os.environ.get("PTRADE_EXPECTATION_DATA_DIR", "").strip()
    if override:
        return override
    return os.path.join(_path_root, "data")


def cache_path() -> str:
    return os.path.join(data_dir(), "tmp", "calendar.json")


def load_trade_dates() -> set:
    """读取 data/tmp/calendar.json 中的交易日集合；失败/缺失返回空 set。

    兼容两种格式：{"data":{"item":[{"date":"YYYY-MM-DD",...},...]}} 或 "YYYY-MM-DD" 字符串数组。
    """
    cp = cache_path()
    if not os.path.isfile(cp):
        return set()
    try:
        with open(cp, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception:
        return set()
    rows = []
    if isinstance(payload, dict):
        item = payload.get("data") or payload
        rows = item.get("item") if isinstance(item, dict) and isinstance(item.get("item"), list) else []
        if not rows and isinstance(item, list):
            rows = item
    elif isinstance(payload, list):
        rows = payload
    out = set()
    for row in rows:
        raw = row if isinstance(row, str) else (row or {}).get("date") or (row or {}).get("date_ms") or ""
        raw = str(raw)
        try:
            if raw.isdigit() and len(raw) == 8:
                out.add(_dt.date(int(raw[:4]), int(raw[4:6]), int(raw[6:8])))
            elif raw:
                out.add(_dt.date.fromisoformat(raw[:10]))
        except (ValueError, TypeError):
            continue
    return out


def is_trading_day(d) -> bool:
    """保守判断某日是否为 A 股交易日。

    优先权威缓存（含节假日）；缓存缺失或目标晚于缓存时按工作日放宽。
    """
    if isinstance(d, _dt.datetime):
        d = d.date()
    elif isinstance(d, str):
        d = _dt.date.fromisoformat(str(d)[:10])
    else:
        d = d
    if d.weekday() >= 5:
        return False
    days = load_trade_dates()
    if not days:
        return True
    if d in days:
        return True
    if d < max(days):
        return False
    return True


def previous_trading_day(d) -> _dt.date:
    if isinstance(d, _dt.datetime):
        d = d.date()
    elif isinstance(d, str):
        d = _dt.date.fromisoformat(str(d)[:10])
    n = d - _dt.timedelta(days=1)
    while not is_trading_day(n):
        n -= _dt.timedelta(days=1)
    return n


def next_trading_day(d) -> _dt.date:
    if isinstance(d, _dt.datetime):
        d = d.date()
    elif isinstance(d, str):
        d = _dt.date.fromisoformat(str(d)[:10])
    n = d + _dt.timedelta(days=1)
    while not is_trading_day(n):
        n += _dt.timedelta(days=1)
    return n