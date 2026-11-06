# -*- coding: utf-8 -*-
"""v1.45 一分钟冲涨停 L2 首帧消费 + 两分钟上攻第二根收价确认回归测试。"""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import time

import pytest


ROOT = Path(__file__).resolve().parents[1]
STRATEGY_PATH = ROOT / "strategies" / "buysell_core" / "strategy.py"


def _load_strategy():
    spec = importlib.util.spec_from_file_location("buysell_core_v145_test", STRATEGY_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.BLS = dict(mod.BLS)
    return mod


def _logger():
    logs = []
    return SimpleNamespace(info=lambda msg: logs.append(msg), error=lambda msg: None,
                           warning=lambda msg: None), logs


def _ms_before(now, secs):
    t0 = now - secs
    lt = time.localtime(t0)
    return str(int(time.strftime('%Y%m%d%H%M%S', lt)) * 1000 + int(t0 % 1 * 1000))


@pytest.fixture
def mod():
    m = _load_strategy()
    m.log, m._logs = _logger()
    m._sn = lambda sec: sec
    m._hhmm = lambda: "09:35"
    m.last_px = lambda sec: 10.0
    m.g = SimpleNamespace(
        spot={"A.XSHE": {"up_px": 10.0}},
        first_zt={},
    )
    return m


def test_limit_1m_tx_hits_within_window(mod):
    mod.g.first_zt["A.XSHE"] = {"ms": _ms_before(time.time(), 30), "ts": time.time(), "src": "tx"}
    assert mod._limit_up_within_1m("A.XSHE") is True
    assert any("[limit-1m]" in x and "src=tx" in x for x in mod._logs)


def test_limit_1m_tx_rejects_stale_outside_legacy(mod):
    mod.g.first_zt["A.XSHE"] = {"ms": _ms_before(time.time(), 90), "ts": time.time(), "src": "tx"}
    assert mod._limit_up_within_1m("A.XSHE") is False


def test_limit_1m_tx_stale_falls_back_legacy(mod):
    mod.g.first_zt["A.XSHE"] = {"ms": _ms_before(time.time(), 90), "ts": time.time(), "src": "tx"}
    mod._hhmm = lambda: "09:31"
    assert mod._limit_up_within_1m("A.XSHE") is True
    assert any("[limit-1m]" in x and "src=legacy" in x for x in mod._logs)


def test_limit_1m_missing_first_zt_legacy_window_only(mod):
    assert mod._limit_up_within_1m("A.XSHE") is False      # 09:35 非 legacy 窗口
    mod._hhmm = lambda: "09:31"
    assert mod._limit_up_within_1m("A.XSHE") is True       # 数据缺失回退时段窗口
    mod._hhmm = lambda: "09:33"
    assert mod._limit_up_within_1m("A.XSHE") is False


def test_limit_1m_reboard_within_window(mod):
    mod.g.first_zt["A.XSHE"] = {
        "ms": _ms_before(time.time(), 90), "ts": time.time(), "src": "tx",
        "last_reboard_ts": time.time() - 20,
    }
    assert mod._limit_up_within_1m("A.XSHE") is True
    assert any("[limit-1m]" in x and "src=reboard" in x for x in mod._logs)


def test_limit_1m_snap_ms_hits(mod):
    mod.g.first_zt["A.XSHE"] = {"ms": _ms_before(time.time(), 10), "ts": time.time(), "src": "snap"}
    assert mod._limit_up_within_1m("A.XSHE") is True


def test_limit_1m_price_below_threshold_rejected(mod):
    mod.g.first_zt["A.XSHE"] = {"ms": _ms_before(time.time(), 10), "ts": time.time(), "src": "tx"}
    mod.last_px = lambda sec: 9.97
    assert mod._limit_up_within_1m("A.XSHE") is False


def test_limit_1m_tx_disabled_uses_legacy(mod):
    mod.BLS["limit_1m_use_tx"] = False
    mod.g.first_zt["A.XSHE"] = {"ms": _ms_before(time.time(), 10), "ts": time.time(), "src": "tx"}
    assert mod._limit_up_within_1m("A.XSHE") is False      # 09:35 不在 legacy 窗口
    mod._hhmm = lambda: "09:31"
    assert mod._limit_up_within_1m("A.XSHE") is True


def _m1_df(closes, highs):
    import pandas as pd
    n = len(closes)
    return pd.DataFrame({"open": [10.0] * n, "high": highs, "close": closes})


def test_two_1m_requires_second_close_above_first(mod):
    mod.get_price = lambda sec, start_date=None, end_date=None, count=8, frequency="1m": \
        _m1_df([10.05, 10.10], [10.30, 10.35])
    assert mod._calc_two_1m_break("A.XSHE") is True


def test_two_1m_rejects_flat_or_lower_second_close(mod):
    mod.get_price = lambda sec, start_date=None, end_date=None, count=8, frequency="1m": \
        _m1_df([10.05, 10.00], [10.30, 10.40])
    assert mod._calc_two_1m_break("A.XSHE") is False


def test_two_1m_close_up_disabled_keeps_old_behavior(mod):
    mod.BLS["two_1m_close_up"] = False
    mod.get_price = lambda sec, start_date=None, end_date=None, count=8, frequency="1m": \
        _m1_df([10.05, 10.00], [10.30, 10.40])
    assert mod._calc_two_1m_break("A.XSHE") is True


def test_two_1m_fails_when_last_bar_below_threshold(mod):
    mod.get_price = lambda sec, start_date=None, end_date=None, count=8, frequency="1m": \
        _m1_df([10.05, 10.06], [10.30, 10.08])
    assert mod._calc_two_1m_break("A.XSHE") is False
