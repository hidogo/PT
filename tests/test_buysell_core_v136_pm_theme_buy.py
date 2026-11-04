# -*- coding: utf-8 -*-
"""v1.36 午后新题材前排试点 / 午后快速刷新 / 滚动窗口发酵识别回归测试。"""
import importlib.util
import time
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
STRATEGY_PATH = ROOT / "strategies" / "buysell_core" / "strategy.py"


def _load_strategy():
    spec = importlib.util.spec_from_file_location("buysell_core_v136_pm_theme_test", STRATEGY_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.BLS = dict(mod.BLS)
    return mod


def _logger():
    logs = []
    return SimpleNamespace(info=lambda msg: logs.append(msg), error=lambda msg: None,
                           warning=lambda msg: None), logs


def _daily():
    d = {"bought": [], "bought_board": [], "bought_kind": {}, "sold": []}
    for k in ("ma5", "core", "elastic_arb", "elastic_top"):
        d["bought_" + k] = []
    return d


@pytest.fixture
def mod():
    m = _load_strategy()
    m.log, m._logs = _logger()
    m._sn = lambda sec: sec
    m._norm_sec = lambda code: code
    m._save_state = lambda: None
    m._warn = lambda msg: None
    m.get_trading_day = lambda: "2026-11-04"
    m.g = SimpleNamespace(
        daily=_daily(),
        buy_log={},
        spot={},
        first_zt={},
        zt_lianban={},
        zt_theme={},
        boards={},
        stock_boards={},
        zt_new_cache={},
        zt_ferment_cache={},
        zt_ferment_stage={},
        zt_unmapped_n=0,
        zt_dyn_cache={},
        near_scan={},
        pool_static=[],
        watch=[],
        exp_file={},
        skip_log_ts={},
        lb_senti={},
        tick_buy_event_seen={},
    )
    return m


def _pm_stubs(mod, ferment=None, buy_slot_ok=None):
    mod._hhmm = lambda: "13:10"
    mod.trade_open = lambda sec: True
    mod._is_st = lambda sec: False
    mod._is_one_word_open = lambda sec: False
    mod._block_sealed_buy = lambda sec: False
    mod._mid_board_avoid = lambda sec: False
    mod._dyn_theme_ferment = lambda: ferment if ferment is not None else {
        "T1": {"confirmed": True, "stage": "confirmed", "burst_front": "B.XSHG",
               "front": "A.XSHG", "burst_count": 2, "burst_span_ms": 300000}}
    mod._new_themes_of = lambda sec: ["T1"]
    mod.last_px = lambda sec: 10.0
    mod._two_1m_break = lambda sec: True
    mod._limit_up_within_1m = lambda sec: False
    mod._vwap_follow_up = lambda sec: True
    mod._l2_big_ok = lambda sec: True
    mod._l2_big_ratio = lambda sec: 0.15
    mod._lb_senti_gate_apply = lambda sec, action: True
    mod._ld_theme_hit = lambda sec: {}
    mod._order_limit = lambda sec, side, mode: 10.2
    mod._buy_slot_ok = buy_slot_ok or (lambda kind: True)
    calls = []
    mod.place_order = lambda context, sec, side, note="", mode="", ratio=0.0: (
        calls.append({"sec": sec, "note": note, "mode": mode, "ratio": ratio}) or True)
    mod._pm_calls = calls
    mod.g.spot["B.XSHG"] = {"up_px": 11.0, "preclose_px": 9.5}
    return mod


def test_fast_window_afternoon_and_morning(mod):
    mod._min_age = lambda: 210
    mod._hhmm = lambda: "13:15"
    assert mod._fast_window() is True
    mod._hhmm = lambda: "13:31"
    assert mod._fast_window() is False
    mod._hhmm = lambda: "12:59"
    assert mod._fast_window() is False
    mod._min_age = lambda: 5
    mod._hhmm = lambda: "09:45"
    assert mod._fast_window() is True


def test_source_limit_fast_in_afternoon_window(mod):
    mod._min_age = lambda: 210
    mod._hhmm = lambda: "13:15"
    assert mod._source_limit("board") == float(mod.BLS["frame_board_limit_fast"])
    assert mod._source_limit("hist1d") == float(mod.BLS["frame_hist1d_limit_fast"])
    assert mod._source_limit("hist1d", prio=1) == float(mod.BLS["frame_hist1d_prio_limit_fast"])
    assert mod._source_limit("m1") == float(mod.BLS["frame_m1_limit_fast"])
    mod._hhmm = lambda: "13:35"
    assert mod._source_limit("board") == float(mod.BLS["frame_board_limit_afternoon"])
    assert mod._source_limit("hist1d", prio=1) == float(mod.BLS["frame_hist1d_prio_limit_afternoon"])


def test_ttl_fast_in_afternoon_window(mod):
    mod._min_age = lambda: 210
    mod._hhmm = lambda: "13:15"
    assert mod._board_refresh_ttl() == pytest.approx(3.0)
    assert mod._market_red_ttl() == pytest.approx(30.0)
    assert mod._ld_ttl() == pytest.approx(15.0)
    mod._hhmm = lambda: "13:35"
    assert mod._board_refresh_ttl() == pytest.approx(60.0)
    assert mod._market_red_ttl() == pytest.approx(60.0)
    assert mod._ld_ttl() == pytest.approx(120.0)


def test_ferment_rolling_window_afternoon_cluster(mod):
    day = 20261104093000000
    mod.g.first_zt = {
        "A.XSHG": {"ms": day + 5 * 60000, "ts": time.time(), "src": "tx", "day": "2026-11-04"},
        "B.XSHG": {"ms": day + 335 * 60000, "ts": time.time(), "src": "tx", "day": "2026-11-04"},
        "C.XSHG": {"ms": day + 340 * 60000, "ts": time.time(), "src": "tx", "day": "2026-11-04"},
    }
    mod._today_zt = lambda sec: True
    mod._is_one_word_open = lambda sec: False
    mod._new_themes_of = lambda sec: ["T1"]
    mod._dyn_theme_status = lambda: {"T1": {"leader": "A.XSHG", "max_board_dyn": 2}}
    out = mod._dyn_theme_ferment()
    d = out["T1"]
    assert d["confirmed"] is True
    assert d["stage"] in ("confirmed", "hot")
    assert d["burst_count"] == 2
    assert d["burst_front"] == "B.XSHG"
    assert d["front"] == "A.XSHG"   # 存量龙头仍为全局前排，午后簇前排单独授 burst_front


def test_pm_theme_buy_elastic_fallback_when_board_slots_used(mod):
    mod = _pm_stubs(mod, buy_slot_ok=lambda kind: kind == "elastic_arb")
    ctx = SimpleNamespace(portfolio=SimpleNamespace(positions={}))
    assert mod._try_pm_theme_buy(ctx, event_sec="B.XSHG") is True
    assert len(mod._pm_calls) == 1
    assert mod._pm_calls[0]["mode"] == "chase"
    assert mod._pm_calls[0]["ratio"] == pytest.approx(0.10)
    assert "B.XSHG" in mod.g.daily["bought_elastic_arb"]
    assert any("[pm-theme]" in x for x in mod._logs)


def test_pm_theme_buy_board_path_when_slot_available(mod):
    mod = _pm_stubs(mod, buy_slot_ok=lambda kind: True)
    ctx = SimpleNamespace(portfolio=SimpleNamespace(positions={}))
    assert mod._try_pm_theme_buy(ctx, event_sec="B.XSHG") is True
    assert mod._pm_calls[0]["mode"] == "sweep"
    assert mod._pm_calls[0]["ratio"] == pytest.approx(0.20)
    assert "B.XSHG" in mod.g.daily["bought_board"]


def test_pm_theme_buy_window_gate(mod):
    mod = _pm_stubs(mod)
    mod._hhmm = lambda: "13:35"
    ctx = SimpleNamespace(portfolio=SimpleNamespace(positions={}))
    assert mod._try_pm_theme_buy(ctx, event_sec="B.XSHG") is False
    assert mod._pm_calls == []


def test_pm_theme_buy_not_front_skip(mod):
    ferment = {"T1": {"confirmed": True, "stage": "confirmed", "burst_front": "C.XSHG",
                      "front": "A.XSHG", "burst_count": 2, "burst_span_ms": 300000}}
    mod = _pm_stubs(mod, ferment=ferment)
    ctx = SimpleNamespace(portfolio=SimpleNamespace(positions={}))
    assert mod._try_pm_theme_buy(ctx, event_sec="B.XSHG") is False
    assert mod._pm_calls == []
    assert any("非午后题材窗口前排" in x for x in mod._logs)


def test_pm_theme_buy_sealed_skip(mod):
    mod = _pm_stubs(mod)
    mod._block_sealed_buy = lambda sec: True
    ctx = SimpleNamespace(portfolio=SimpleNamespace(positions={}))
    assert mod._try_pm_theme_buy(ctx, event_sec="B.XSHG") is False
    assert mod._pm_calls == []


def test_pm_theme_tick_near_event_dispatch(mod):
    seen = []
    mod._hhmm = lambda: "13:10"
    mod._pool_exp_priority = lambda sec: (1, 2)
    mod._try_new_theme_sweep = lambda context, event_sec=None: False
    mod._try_elastic_arb_buy = lambda context, event_sec=None: False
    mod._try_pm_theme_buy = lambda context, event_sec=None: (seen.append(event_sec) or False)
    ctx = SimpleNamespace(portfolio=SimpleNamespace(positions={}))
    mod._run_tick_buy_events(ctx, [{"kind": "near", "sec": "B.XSHG"}])
    assert seen == ["B.XSHG"]
